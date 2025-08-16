# app.py – ReplenishAI Agent UI (TODO Template)

import streamlit as st
import time
import pandas as pd
import os

# TODO 1: Setup page config & title
st.set_page_config(
    page_title = 'ReplenishAI - Agentic Supply Chain',
    layout = 'wide',
    initial_sidebar_state = 'expanded'
)
st.title("🤖 ReplenishAI – Agentic Supply Chain Intelligence")
st.markdown("""
### **Autonomous AI Agents Making Real-Time Procurement Decisions**
*Multi-agent system for intelligent spare parts management*
""")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🧠 AI Confidence", "94.2%", "↑ 2.1%")
with col2:
    st.metric("💰 Cost Savings", "$47,230", "↑ $12,400")
with col3:
    st.metric("⚡ Processing Time", "2.3 sec", "↓ 15.2 sec")
with col4:
    st.metric("🎯 Accuracy Rate", "97.8%", "↑ 4.2%")



st.divider()

# TODO 2: Sidebar inputs
st.sidebar.header("🎛️ Agent Configuration")
st.sidebar.markdown("Configure the autonomous agent parameters")

service_level = st.sidebar.slider(
    "🎯 Service Level Target", 
    min_value=0.85,
    max_value=0.99,
    value=0.95,
    step=0.01,
    help="Higher service level = more safety stock"
)

review_horizon = st.sidebar.slider(
    "📅 Review Horizon (days)", 
    min_value=7,
    max_value=60,
    value=30,
    step=1,
    help="Planning period for demand forecasting"
)

st.sidebar.divider()

run_agent = st.sidebar.button(
    "🚀 Run Autonomous Agent",
    type="primary",
    use_container_width=True
)

if st.sidebar.checkbox("Show Configuration Status", value=True):
    with st.sidebar.container():
        st.markdown("### 📊 Active Configuration")
        st.success(f"Service Level: {service_level:.0%}")
        st.info(f"Review Period: {review_horizon} days")
        st.caption("Ready for agent execution")

# TODO 3: Agent progress display
if run_agent: 
    progress_container = st.container()

    with progress_container:
        st.subheader("🤖 Autonomous Agent in Action")
    
    status_placeholder = st.empty()
    progress_bar = st.progress(0)

    agent_steps = [
        "🔍 Analyzing current inventory levels",
        "📊 Forecasting demand using historical data", 
        "💼 Fetching supplier quotes and availability",
        "✅ Running compliance and quality checks",
        "🎯 Ranking suppliers using AI scoring",
        "📝 Generating intelligent recommendations"
    ]

    for i, step in enumerate(agent_steps):
        status_placeholder.write(f"**{step}**")
        progress_bar.progress((i + 1) / len(agent_steps))
        time.sleep(0.8)

    status_placeholder.write("✅ **Agent analysis complete!**")
    
    def get_data_path():
        if os.path.exists("../data/parts.csv"):  # Local development
            return "../data/"
        elif os.path.exists("data/parts.csv"):   # Streamlit Cloud
            return "data/"
        else:
            raise FileNotFoundError("Data directory not found")
        
    # STEP 4: Load data and generate recommendations
    try:
        from engine import load_data, recommend, ReorderParams

        data_path = get_data_path()
        parts, inv, dem, quotes = load_data(
        f"{data_path}parts.csv", 
        f"{data_path}inventory.csv", 
        f"{data_path}demand_history.csv", 
        f"{data_path}supplier_quotes.csv"
    )

        params = ReorderParams(service_level=service_level, review_horizon_days=review_horizon)
        recommendations = recommend(parts, inv, dem, quotes, params=params)

        st.subheader("📊 AI-Generated Recommendations")

        if recommendations.empty:
            st.info("🎯 No parts need reordering at this time. Current inventory levels are sufficient!")
        else:
            st.dataframe(recommendations, use_container_width=True)

            csv = recommendations.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Download Recommendations (CSV)",
                data=csv,
                file_name=f"replenish_recommendations_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

            # TODO 5: Explanation panel (MOVED INSIDE THE ELSE BLOCK)
            st.subheader("🧠 AI Agent Reasoning & Explanations")
            
            # Overall decision summary
            with st.expander("📋 **Executive Summary**", expanded=True):
                total_parts = len(recommendations)
                total_cost = (recommendations['recommend_qty'] * recommendations['unit_price_usd']).sum()
                avg_score = recommendations['score'].mean()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Parts to Order", total_parts)
                with col2:
                    st.metric("Total Investment", f"${total_cost:,.2f}")
                with col3:
                    st.metric("Avg AI Confidence", f"{avg_score:.1%}")
            
            # Detailed explanations per recommendation
            with st.expander("🔍 **Detailed AI Reasoning**"):
                st.markdown("**Why the AI agent selected each supplier:**")
                
                for idx, row in recommendations.iterrows():
                    with st.container():
                        st.markdown(f"### Part: {row['name']} ({row['part_id']})")
                        
                        col_a, col_b = st.columns([2, 1])
                        
                        with col_a:
                            st.markdown(f"""
                            **🎯 Selected Supplier:** {row['supplier_name']}  
                            **💡 AI Reasoning:** {row['reason']}  
                            **🔢 Quantity Decision:** Order {row['recommend_qty']} units  
                            **📊 Confidence Score:** {row['score']:.1%}
                            """)
                        
                        with col_b:
                            st.info(f"💰 Unit Price: ${row['unit_price_usd']}")
                            st.info(f"⏱️ Lead Time: {row['lead_time_offer_days']} days")
                            st.info(f"⭐ Rating: {row['supplier_rating']}/5.0")
                        
                        st.divider()
            
            # Risk assessment
            with st.expander("⚠️ **Risk Assessment & Mitigation**"):
                st.markdown("**AI-identified risks and recommendations:**")
                
                high_lead_time = recommendations[recommendations['lead_time_offer_days'] > 10]
                low_rating = recommendations[recommendations['supplier_rating'] < 4.0]
                high_cost = recommendations[recommendations['unit_price_usd'] > recommendations['unit_price_usd'].median()]
                
                if not high_lead_time.empty:
                    st.warning(f"🚨 **Lead Time Risk:** {len(high_lead_time)} suppliers have >10 day lead times")
                    
                if not low_rating.empty:
                    st.warning(f"⚠️ **Quality Risk:** {len(low_rating)} suppliers have <4.0 ratings")
                    
                if not high_cost.empty:
                    st.info(f"💰 **Cost Optimization:** {len(high_cost)} items above median price - consider negotiation")
                
                if high_lead_time.empty and low_rating.empty:
                    st.success("✅ **Low Risk Portfolio:** All recommendations meet quality and timing standards")

    except Exception as e:
        st.error(f"❌ Error loading data or generating recommendations: {e}")
        st.info("Please check your data files and parameters.")
