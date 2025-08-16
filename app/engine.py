
"""
ReplenishAI - Core engine (TODO version)

Implement the deterministic logic for forecasting, safety stock, reorder point, and recommendations.
Fill every TODO and make tests pass (pytest). Keep functions pure and side-effect free.
"""

from dataclasses import dataclass
from typing import Tuple
import pandas as pd
import numpy as np

DEFAULT_SERVICE_LEVEL = 0.95
DEFAULT_LEAD_TIME_DAYS = 14

@dataclass
class ReorderParams:
    review_horizon_days: int = 30
    service_level: float = DEFAULT_SERVICE_LEVEL

# --------- TODO 1: simple moving average ---------
def sma(series: pd.Series, window: int = 28) -> float:
    """Return the mean of the last `window` observations (drop NaNs).

    Example: if series tail is [2,3,NaN,5], SMA over 4 = (2+3+5)/3.
    If no numeric values are present, return 0.0.
    """
    # get the last 'window' values
    tail_data = series.tail(window)

    #drop NaN values
    clean_data = tail_data.dropna()

    # if no numeric values
    if len(clean_data) == 0:
        return 0.0
    
    return clean_data.mean()

# --------- TODO 2: safety stock ---------
def safety_stock(daily_demand: float, lead_time_days: int, service_level: float = DEFAULT_SERVICE_LEVEL) -> float:
    """Approximate safety stock using z * sigma * sqrt(lead_time_days).
    Use z = {0.90:1.28, 0.95:1.65, 0.98:2.05, 0.99:2.33} with default 1.65.
    Let sigma ≈ 0.25 * daily_demand (simple proxy for variability).
    Ensure non-negative and handle edge cases (lead_time_days >= 1).
    """
    if lead_time_days < 1 or daily_demand < 0:
        return 0.0
    
    z_scores = {
        0.90: 1.28,
        0.95: 1.65,
        0.98: 2.05,
        0.99: 2.33
    }

    # Get z-score for service level (default to 1.65 if not found)
    z = z_scores.get(service_level, 1.65)

    # Calculate sigma (simple proxy for demand variability)
    sigma = 0.25 * daily_demand

    # Calculate safety stock: z * sigma * sqrt(lead_time_days)
    safety_stock_value = z * sigma * (lead_time_days ** 0.5)
    
    # Ensure non-negative (though should already be positive)
    return max(0.0, safety_stock_value)
# --------- TODO 3: reorder point ---------
def reorder_point(daily_demand: float, lead_time_days: int, ss: float) -> float:
    """ROP = daily_demand * lead_time_days + safety_stock"""
    return daily_demand * lead_time_days + ss

# --------- TODO 4: load data ---------
def load_data(parts_csv: str, inv_csv: str, demand_csv: str, quotes_csv: str):
    """Load CSVs, parse dates, and return (parts, inventory, demand, quotes).
    demand['date'] must be parsed to datetime.
    """

    #Load Parts CSV
    parts = pd.read_csv(parts_csv)

    #Load Inventory CSV
    inventory = pd.read_csv(inv_csv)
    
    #Load Demand CSV and parse 'date' column
    demand = pd.read_csv(demand_csv, parse_dates=['date'])
    
    #Load Quotes CSV
    quotes = pd.read_csv(quotes_csv)

    #Return as tuple in the order specified
    return parts, inventory, demand, quotes

# --------- helper ---------
def _build_daily_demand(dem: pd.DataFrame) -> pd.DataFrame:
    """Aggregate demand to daily qty per part and compute daily_rate using 4-week SMA.
    daily_rate ~ SMA(28).
    """
    agg = dem.groupby(['part_id', 'date'], as_index=False)['qty'].sum()
    rates = agg.groupby('part_id')['qty'].apply(lambda s: sma(s, 28)).reset_index(name='daily_rate')
    return rates

# --------- TODO 5: recommend pipeline ---------
def recommend(parts: pd.DataFrame, inv: pd.DataFrame, dem: pd.DataFrame, quotes: pd.DataFrame,
              params: ReorderParams = ReorderParams()) -> pd.DataFrame:
    """
    Steps (must match tests):
      1) Join inventory + parts + daily demand rates.
      2) Fill missing daily_rate with 0.0; fill missing lead_time_days with DEFAULT_LEAD_TIME_DAYS.
      3) safety_stock -> rop -> net_on_hand = on_hand - reserved -> need_qty = max(rop - net_on_hand, 0), round to int.
      4) Filter rows where need_qty > 0. If none, return empty DataFrame.
      5) Join candidate supplier quotes on part_id.
      6) Hard filters: moq <= need_qty AND lead_time_offer_days <= lead_time_days.
      7) Score candidates with normalized metrics:
         - price_n: lower unit_price_usd is better
         - lt_n:    lower lead_time_offer_days is better
         - rate_n:  higher supplier_rating is better
         score = 0.5*price_n + 0.3*lt_n + 0.2*rate_n
         Use min-max normalization; if range is zero, use 0.5 for that metric.
      8) Pick top-scoring supplier per part.
      9) recommend_qty = max(need_qty, moq). reason string should include price, lead time, and rating.
    Return columns:
      ['part_id','name','supplier_id','supplier_name','recommend_qty','unit_price_usd','lead_time_offer_days','supplier_rating','score','reason']
    """ 
   # Step 1: Get daily demand rates and join everything
    daily_rates = _build_daily_demand(dem)

   # Join inventory + parts + daily demand rates. Inventory has part_id, on_had, reserved.
    # Parts has part_id, name. Daily rates has part_id, daily_rate. Merging will create 
    # one row per part with both invetory levels and part details.
    df = inv.merge(parts, on="part_id", how="left")
    #Second Mege. Adds demand forecasting data to the DataFrame.daily_rates has part_id, daily_rate from SMA calculation.
    #Result - now each part has inventory +partinfo + demand forecast
    #how = "left" ensures we keep all inventory parts even if no demand or pats data exists. 
    df = df.merge(daily_rates, on="part_id", how="left")

    # Step 2: Fill missing values. Parts with no demand, assume 0 demand. Use default lead time of 14 
    # days for parts with no lead time data.
    # Fill NaN daily_rate with 0.0, lead_time_days with DEFAULT_LEAD_TIME_DAYS.
    # This ensures we can calculate safety stock and reorder points without NaN issues.
    df["daily_rate"] = df["daily_rate"].fillna(0.0)
    df["lead_time_days"] = df["lead_time_days"].fillna(DEFAULT_LEAD_TIME_DAYS)

    #Step 3: Calculate safety stock, reorder point, net in hand and need quantity
    
    # For each row calculate safety stock
    df["ss"] = df.apply(lambda row: safety_stock(row['daily_rate'], row['lead_time_days'], params.service_level), axis=1 )
    
    # For each row calculate reorder point
    df['rop'] = df.apply(lambda row: reorder_point(row['daily_rate'], row['lead_time_days'], row['ss']), axis=1)

    # Calculate net on hand
    df['net_on_hand'] = df['on_hand'] - df['reserved']

    # Calculate need quantity(need to order ). Clip will bring it to 0 if negative.
    # Round to int as we cannot order fractional parts.
    # need_qty = max(rop - net_on_hand, 0), round to int.
    # This ensures we only order if we need more than we have on hand.
    # If net_on_hand is greater than rop, need_qty will be 0.
    # If net_on_hand is less than rop, need_qty will be positive.
    # Clip ensures we don't have negative need_qty.
    # Round to int as we cannot order fractional parts.
    # net_on_hand = on_hand - reserved -> need_qty = max(rop - net_on_hand, 0), round to int.
    # net_on_hand is the current stock minus any reserved stock.
    # need_qty is the quantity we need to order to reach the reorder point.
    # If we have enough stock, need_qty will be 0.
    # If we don't have enough stock, need_qty will be positive.
    df['need_qty'] = (df['rop'] - df['net_on_hand']).clip(lower=0).round().astype(int)

    # Step 4: Filter rows where need_qty > 0. If none, return empty DataFrame.
    needs = df[df['need_qty'] > 0].copy()

    # If no parts need ordering, return empty DataFrame with correct columns
    if needs.empty:
        return pd.DataFrame(columns=['part_id','name','supplier_id','supplier_name','recommend_qty','unit_price_usd','lead_time_offer_days','supplier_rating','score','reason'])
    
    # Step 5: Join candidate supplier quotes on part_id.
    # Quotes has part_id, supplier_id, supplier_name, unit_price_usd, lead_time_offer_days, supplier_rating, moq.
    candidates = needs.merge(quotes, on="part_id", how="inner")


    # Step 6: Hard Filters: moq <= need_qty AND lead_time_offer_days <= lead_time_Days
    candidates = candidates[
        (candidates['moq'] <= candidates['need_qty']) & 
        (candidates['lead_time_offer_days'] <= candidates['lead_time_days'])
    ]
    # If no suppliers meet requirements, return empty DataFrame
    if candidates.empty:
        return pd.DataFrame(columns=['part_id','name','supplier_id','supplier_name','recommend_qty','unit_price_usd','lead_time_offer_days','supplier_rating','score','reason'])

    # Step 7: Score candidates with normalized metrics
    # Min-max normalization : (value-min)/(max-min)
    # For price and lead time, lower is better, so we invert the normalization.
    # For supplier rating, higher is better, so we use normal normalization.
   
    # Handle case where all values are the same(range = 0)
    price_min, price_max = candidates["unit_price_usd"].min(), candidates["unit_price_usd"].max()
    lt_min, lt_max = candidates["lead_time_offer_days"].min(), candidates["lead_time_offer_days"].max()
    rate_min, rate_max = candidates["supplier_rating"].min(), candidates["supplier_rating"].max()
    
    #Normalize price: lower is better
    if price_max - price_min > 0:
        candidates["price_n"] = 1 - (candidates["unit_price_usd"] - price_min) / (price_max - price_min) 
    else:
        candidates["price_n"] = 0.5
    
    #Normallize lead time: lower is better
    if lt_max - lt_min > 0:
        candidates["lt_n"] = 1 - (candidates["lead_time_offer_days"] - lt_min) / (lt_max - lt_min)
    else:
        candidates["lt_n"] = 0.5
    
    #Normalize supplier rating: higher is better
    if rate_max - rate_min > 0:
        candidates["rate_n"] = (candidates["supplier_rating"] - rate_min) / (rate_max - rate_min)
    else:
        candidates["rate_n"] = 0.5
        
    # Calculate score: 0.5*price_n + 0.3*lt_n + 0.2*rate_n
    candidates["score"] = 0.5 * candidates["price_n"] + 0.3 * candidates["lt_n"] + 0.2 * candidates["rate_n"]
    
    # Step 8: Pick the top scoring supplier per part
    best = candidates.loc[candidates.groupby('part_id')['score'].idxmax()].copy()

    #Step 9: recommend_qty = max(need_qty, moq) reason string should include price, lead time, and rating.
    best['recommend_qty'] = best[['need_qty', 'moq']].max(axis=1)

    # Create reason string
    best['reason'] = best.apply(lambda row: f"Price: ${row['unit_price_usd']:.2f}, Lead time: {row['lead_time_offer_days']} days, Rating: {row['supplier_rating']}/5.0", axis=1)

    # Select and order final columns
    candidates = best[['part_id','name','supplier_id','supplier_name','recommend_qty','unit_price_usd','lead_time_offer_days','supplier_rating','score','reason']].copy()

    return candidates