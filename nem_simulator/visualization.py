"""
Interactive Visualization Engine
=================================
Generates responsive Plotly dashboards visualizing dispatch merit order,
wholesale spot prices, battery state-of-charge, and emissions across scenarios.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .model import DispatchResult

# Color Palette adhering to AEMO & DCCEEW Standards
FUEL_COLORS = {
    'Black Coal': '#2d3748',
    'Gas CCGT': '#dd6b20',
    'Gas OCGT': '#e53e3e',
    'Gas Peaker': '#e53e3e',
    'Solar': '#ecc94b',
    'Wind': '#38a169',
    'Pumped Hydro': '#3182ce',
    'Battery BESS (Discharge)': '#805ad5',
    'Waratah Super Battery System (Discharge)': '#805ad5',
    'NSW Distributed Grid Batteries (Discharge)': '#9f7aea',
    'Shoalhaven Pumped Hydro Scheme (Discharge)': '#3182ce',
    'NSW Long Duration Storage (8h+) (Discharge)': '#2b6cb0',
    'Victoria-NSW Interconnector (VNI)': '#d69e2e',
    'Queensland-NSW Interconnector (QNI)': '#4fd1c5'
}

SCENARIO_COLORS = {
    'Baseline_2024': '#3182ce',
    'Eraring_Retirement_Unfirmed': '#e53e3e',
    'NSW_Roadmap_2030': '#38a169'
}

def generate_interactive_dashboard(
    results: Dict[str, DispatchResult],
    output_html_path: str
) -> str:
    """
    Generate an executive multi-panel interactive HTML dashboard.
    """
    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
    
    # 4 Subplot layout:
    # 1. Dispatch Stack for Roadmap 2030 (Top Left)
    # 2. Wholesale Spot Price Comparison ($/MWh) (Top Right)
    # 3. BESS & Storage SoC Profiles (%) (Bottom Left)
    # 4. Carbon Emissions Trajectory (tCO2-e) (Bottom Right)
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "<b>1. Generation Dispatch Stack by Fuel — NSW Roadmap 2030 (MW)</b>",
            "<b>2. Wholesale Spot Price Curve Comparison ($/MWh)</b>",
            "<b>3. Storage State-of-Charge Dynamics (BESS & Pumped Hydro)</b>",
            "<b>4. Interval Carbon Emissions Comparison (tCO2-e)</b>"
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )

    # -------------------------------------------------------------
    # Panel 1: Stacked Generation Dispatch for Roadmap 2030
    # -------------------------------------------------------------
    roadmap_res = results.get('NSW_Roadmap_2030') or list(results.values())[0]
    df_fuel = roadmap_res.generation_by_fuel_df
    intervals = list(range(1, roadmap_res.intervals + 1))
    hours = [f"{int((i-1)*0.5):02d}:{'30' if (i-1)%2 else '00'}" for i in intervals]

    for col in df_fuel.columns:
        # Exclude charging traces (displayed in storage panel)
        if '(Charge)' in col:
            continue
        color = FUEL_COLORS.get(col, '#718096')
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=df_fuel[col],
                name=col,
                stackgroup='one',
                mode='lines',
                line=dict(width=0.5, color=color),
                fillcolor=color,
                hovertemplate='%{y:.0f} MW'
            ),
            row=1, col=1
        )

    # Add Demand Line on Panel 1
    demand = roadmap_res.prices_df['demand_mw']
    fig.add_trace(
        go.Scatter(
            x=hours,
            y=demand,
            name='Operational Demand (MW)',
            mode='lines',
            line=dict(color='#1a202c', width=2.5, dash='dash'),
            hovertemplate='%{y:.0f} MW'
        ),
        row=1, col=1
    )

    # -------------------------------------------------------------
    # Panel 2: Wholesale Spot Price Curve ($/MWh)
    # -------------------------------------------------------------
    for sc_name, res in results.items():
        color = SCENARIO_COLORS.get(sc_name, '#4a5568')
        prices = res.prices_df['clearing_price_per_mwh']
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=prices,
                name=f"{sc_name} Price",
                mode='lines+markers',
                line=dict(color=color, width=2.2),
                marker=dict(size=4),
                hovertemplate='%{y:.2f} $/MWh'
            ),
            row=1, col=2
        )

    # -------------------------------------------------------------
    # Panel 3: Storage State-of-Charge (%)
    # -------------------------------------------------------------
    if not roadmap_res.storage_soc_df.empty:
        for col in roadmap_res.storage_soc_df.columns:
            if '(%)' in col:
                clean_name = col.replace(' SoC (%)', '')
                fig.add_trace(
                    go.Scatter(
                        x=hours,
                        y=roadmap_res.storage_soc_df[col],
                        name=f"{clean_name} SoC",
                        mode='lines',
                        line=dict(width=2),
                        hovertemplate='%{y:.1f}%'
                    ),
                    row=2, col=1
                )

    # -------------------------------------------------------------
    # Panel 4: Carbon Emissions per Interval (tCO2-e)
    # -------------------------------------------------------------
    for sc_name, res in results.items():
        color = SCENARIO_COLORS.get(sc_name, '#4a5568')
        emissions = res.prices_df['emissions_tco2']
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=emissions,
                name=f"{sc_name} Emissions",
                mode='lines',
                line=dict(color=color, width=2),
                hovertemplate='%{y:.0f} tCO2-e'
            ),
            row=2, col=2
        )

    # Layout Aesthetics
    fig.update_layout(
        title={
            'text': "<b>NEM Dispatch & Unit Commitment Simulator — NSW Policy Scenarios</b><br>"
                    "<sup>Linear Programming (HiGHS) Dispatch Optimization & BESS Co-Optimization | Author: Dr. Md Mahmudur Rahman</sup>",
            'x': 0.05,
            'y': 0.96,
            'xanchor': 'left',
            'yanchor': 'top',
            'font': {'size': 20, 'color': '#002664'}
        },
        template='plotly_white',
        height=950,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.12,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(t=100, b=120, l=60, r=60)
    )

    fig.update_xaxes(title_text="Trading Interval (Time of Day)", row=2, col=1)
    fig.update_xaxes(title_text="Trading Interval (Time of Day)", row=2, col=2)
    fig.update_yaxes(title_text="Generation / Demand (MW)", row=1, col=1)
    fig.update_yaxes(title_text="Spot Clearing Price ($/MWh)", row=1, col=2)
    fig.update_yaxes(title_text="State of Charge (%)", row=2, col=1)
    fig.update_yaxes(title_text="Emissions (tCO2-e)", row=2, col=2)

    fig.write_html(output_html_path)
    return output_html_path
