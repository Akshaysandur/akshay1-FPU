from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from PIL import Image

from dashboard.config import LAYOUT_IMAGE, PATH_COORDINATES, PATH_GRAPH, STATIONS
from dashboard.models import AMRState


def build_factory_figure(amrs: dict[str, AMRState]) -> go.Figure:
    image = Image.open(Path(LAYOUT_IMAGE))
    width, height = image.size
    fig = go.Figure()

    for start, neighbors in PATH_GRAPH.items():
        for neighbor in neighbors:
            if start < neighbor:
                x0, y0 = PATH_COORDINATES[start]
                x1, y1 = PATH_COORDINATES[neighbor]
                fig.add_trace(
                    go.Scatter(
                        x=[x0, x1],
                        y=[height - y0, height - y1],
                        mode="lines",
                        line={"color": "rgba(31, 78, 121, 0.28)", "width": 5},
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

    fig.add_layout_image(
        dict(
            source=image,
            x=0,
            y=height,
            sizex=width,
            sizey=height,
            xref="x",
            yref="y",
            sizing="stretch",
            layer="below",
            opacity=1.0,
        )
    )

    station_text = {
        "Loading": "L.S",
        "Machine1": "Machine 1",
        "Machine2": "Machine 2",
        "Machine3": "Machine 3",
        "Machine4": "Machine 4",
        "Unloading": "UN.L",
        "Charging": "Charging",
    }
    for station, (x, y) in STATIONS.items():
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[height - y],
                mode="text",
                text=[station_text[station]],
                textposition="top center",
                textfont={"color": "#0f172a", "size": 13},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    status_colors = {
        "Idle": "#2563eb",
        "Moving": "#3182ce",
        "Charging": "#7c3aed",
        "Processing": "#dd6b20",
    }
    for amr in amrs.values():
        fig.add_trace(
            go.Scatter(
                x=[amr.x],
                y=[height - amr.y],
                mode="markers+text",
                marker={
                    "size": 18,
                    "color": status_colors.get(amr.status, "#1a202c"),
                    "symbol": "circle",
                    "line": {"color": "#ffffff", "width": 2},
                },
                text=[amr.amr_id],
                textposition="bottom center",
                name=amr.amr_id,
                hovertemplate=(
                    f"{amr.amr_id}<br>Status: {amr.status}<br>Battery: {amr.battery}%"
                    f"<br>Task: {amr.current_task}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=620,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#f8fafc",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
    )
    fig.update_xaxes(visible=False, range=[0, width], fixedrange=True)
    fig.update_yaxes(visible=False, range=[0, height], fixedrange=True, scaleanchor="x", scaleratio=1)
    return fig
