"""
PLEXOS Analyst Terminal Dashboard
=================================
Generates an institutional-grade, responsive HTML dashboard matching the exact
diagnostic visualizations used by energy market analysts at DCCEEW and AEMO.
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .plexos_engine import AnnualPLEXOSResult

def generate_plexos_analyst_dashboard(
    annual_result: AnnualPLEXOSResult,
    output_html_path: str
) -> str:
    """
    Generate an executive annual PLEXOS diagnostic dashboard.
    """
    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)

    res = annual_result
    df_h = res.hourly_results_df
    df_pdc = res.price_duration_curve_df
    df_cf = res.capacity_factors_df

    # 4-panel executive layout
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "<b>1. Annual PLEXOS Price Duration Curve (PDC) — 8,760 Hours</b>",
            "<b>2. Annual Generation Mix by Fuel (GWh)</b>",
            "<b>3. Monthly Average Spot Price vs Peak Demand Profile</b>",
            "<b>4. Asset Capacity Factor & Utilization Benchmark (%)</b>"
        ),
        vertical_spacing=0.14,
        horizontal_spacing=0.09
    )

    # -------------------------------------------------------------
    # 1. Price Duration Curve (PDC) - Logarithmic Scale
    # -------------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=df_pdc['percentage_of_year'],
            y=df_pdc['clearing_price_per_mwh'],
            name='Spot Price Duration',
            mode='lines',
            line=dict(color='#002664', width=2.5),
            hovertemplate='%{x:.1f}% of year: $%{y:.2f}/MWh'
        ),
        row=1, col=1
    )
    # Add NEM Market Price Cap reference line
    fig.add_hline(
        y=17500, line_dash="dash", line_color="#e53e3e",
        annotation_text="Market Price Cap ($17,500)", annotation_position="top right",
        row=1, col=1
    )

    # -------------------------------------------------------------
    # 2. Annual Generation Mix (GWh) Donut / Bar Chart
    # -------------------------------------------------------------
    fuel_s = res.generation_by_fuel_annual_gwh
    # Clean up names
    clean_fuel = {}
    for k, v in fuel_s.items():
        if v > 10.0:
            clean_fuel[k] = v

    fig.add_trace(
        go.Bar(
            x=list(clean_fuel.keys()),
            y=list(clean_fuel.values()),
            name='Annual Energy (GWh)',
            marker_color=['#2d3748', '#38a169', '#ecc94b', '#3182ce', '#dd6b20', '#805ad5', '#e53e3e'],
            hovertemplate='%{x}: %{y:,.1f} GWh'
        ),
        row=1, col=2
    )

    # -------------------------------------------------------------
    # 3. Monthly Average Spot Price & Peak Demand
    # -------------------------------------------------------------
    # Extract month from timestamp
    df_h['month_name'] = pd.to_datetime(df_h['timestamp']).dt.strftime('%b')
    monthly = df_h.groupby('month_name', sort=False).agg({
        'clearing_price_per_mwh': 'mean',
        'demand_mw': 'max'
    }).reset_index()

    # Reorder by calendar month
    month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly['month_idx'] = monthly['month_name'].apply(lambda m: month_order.index(m) if m in month_order else 0)
    monthly = monthly.sort_values('month_idx')

    fig.add_trace(
        go.Bar(
            x=monthly['month_name'],
            y=monthly['clearing_price_per_mwh'],
            name='Monthly Avg Spot Price ($/MWh)',
            marker_color='#005B94',
            yaxis='y3',
            hovertemplate='%{x}: $%{y:.2f}/MWh'
        ),
        row=2, col=1
    )

    # -------------------------------------------------------------
    # 4. Capacity Factor League Table (Top 8 Assets)
    # -------------------------------------------------------------
    top_assets = df_cf.head(8)
    fig.add_trace(
        go.Bar(
            x=top_assets['Capacity_Factor_Pct'],
            y=top_assets['Asset'],
            orientation='h',
            name='Capacity Factor (%)',
            marker_color='#2b6cb0',
            hovertemplate='%{y}: %{x:.1f}% CF'
        ),
        row=2, col=2
    )

    # Styling and Layout
    fig.update_layout(
        title={
            'text': f"<b>PLEXOS 2026 Annual Simulation Report — {res.scenario_name}</b><br>"
                    f"<sup>Total Energy: {res.total_demand_gwh:,.1f} GWh | Total Emissions: {res.total_emissions_mtco2:.2f} Mt CO2 | Total Cost: ${res.total_cost_million_aud:,.1f}M AUD</sup>",
            'x': 0.05,
            'y': 0.97,
            'xanchor': 'left',
            'yanchor': 'top',
            'font': {'size': 20, 'color': '#002664'}
        },
        template='plotly_white',
        height=950,
        showlegend=False,
        margin=dict(t=110, b=60, l=60, r=60)
    )

    fig.update_xaxes(title_text="Percentage of Year (%)", row=1, col=1)
    fig.update_yaxes(title_text="Clearing Price ($/MWh)", type="log", row=1, col=1)
    fig.update_yaxes(title_text="Annual Generation (GWh)", row=1, col=2)
    fig.update_yaxes(title_text="Avg Spot Price ($/MWh)", row=2, col=1)
    fig.update_xaxes(title_text="Capacity Factor (%)", row=2, col=2)
    fig.update_yaxes(autorange="reversed", row=2, col=2)

    fig.write_html(output_html_path)
    return output_html_path
