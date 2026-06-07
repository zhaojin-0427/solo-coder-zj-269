import traceback

import pandas as pd

import dash
from dash import dcc, html, Input, Output, State, dash_table, ALL, ctx
import dash_bootstrap_components as dbc

from data_parser import (
    CATEGORIES, generate_sample_data, parse_contents, filter_dataframe
)
from analyzer import (
    default_budget_config, init_budget_from_history, detect_patterns,
    compute_monthly_budget_series, detect_abnormal_expenses,
    analyze_overspend_causes, simulate_next_month_budget,
    generate_budget_suggestion, compute_budget_execution
)
from charts import (
    empty_fig, make_category_pie, make_budget_progress, make_heatmap,
    make_emotion_scatter, make_trend_chart, make_payment_chart,
    make_budget_comparison_chart, make_cause_distribution_chart,
    make_simulation_chart
)
from ui_components import (
    build_budget_config_panel, build_abnormal_list_table,
    build_overspend_cause_cards, build_budget_simulator_content,
    build_patterns_content, build_budget_suggestion_content
)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.MINTY])
app.title = "预算情景模拟与异常消费归因工作台"
server = app.server


current_df = None
current_msg = ""
current_budget_config = default_budget_config()
current_savings_goal = 0.0


def init_data():
    global current_df, current_msg, current_budget_config, current_savings_goal
    current_df = generate_sample_data()
    current_msg = "已加载示例数据（500条）"
    current_budget_config = init_budget_from_history(current_df)
    total_budget = sum(v['monthly_budget'] for v in current_budget_config.values())
    current_savings_goal = round(total_budget * 0.15, -1)


init_data()


SIDEBAR_STYLE = {
    "padding": "2rem 1rem",
    "backgroundColor": "#f8f9fa",
    "minHeight": "100vh",
}


def build_layout():
    budget_panel = build_budget_config_panel(current_budget_config, current_savings_goal)
    return dbc.Container([
        html.H2(
            [html.Span("💹 ", style={'marginRight': '10px'}),
             "预算情景模拟与异常消费归因工作台"],
            className="text-center my-4",
            style={'color': '#343a40', 'fontWeight': 'bold'}
        ),

        dbc.Card([
            dbc.CardHeader("📂 数据上传", className="bg-primary text-white"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dcc.Upload(
                            id='upload-data',
                            children=dbc.Card([
                                dbc.CardBody([
                                    html.H5("拖拽 CSV/Excel 到此处或点击上传", className="text-center"),
                                    html.P(
                                        "支持列：日期/时间、金额/价格、类别/分类、支付方式、情绪标签、场景、消费目标、备注",
                                        className="text-center text-muted small mt-2 mb-0"
                                    )
                                ])
                            ], className="border-primary border-dashed"),
                            multiple=False,
                            style={'width': '100%', 'cursor': 'pointer'}
                        ),
                        html.Div(id='file-status', className="mt-2 small text-info fw-bold")
                    ], width=8),
                    dbc.Col([
                        dbc.Button(
                            "使用示例数据", id='use-sample',
                            color="secondary", className="w-100 mt-3", size="lg"
                        ),
                        html.P(
                            "点击按钮加载示例消费记录进行体验",
                            className="text-center text-muted small mt-2"
                        )
                    ], width=4)
                ])
            ])
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader("🔍 联动筛选", className="bg-info text-white"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([html.Label("月份"), dcc.Dropdown(id='filter-months', multi=True, placeholder="选择月份...")], width=3),
                    dbc.Col([html.Label("消费类别"), dcc.Dropdown(id='filter-categories', multi=True, placeholder="选择类别...")], width=3),
                    dbc.Col([html.Label("支付方式"), dcc.Dropdown(id='filter-payments', multi=True, placeholder="选择支付方式...")], width=3),
                    dbc.Col([html.Label("场景"), dcc.Dropdown(id='filter-scenes', multi=True, placeholder="场景...")], width=1.5),
                    dbc.Col([html.Label("消费目标"), dcc.Dropdown(id='filter-goals', multi=True, placeholder="目标...")], width=1.5),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.Button("重置筛选", id='reset-filter', className="btn btn-outline-secondary mt-3 btn-sm")
                    ])
                ])
            ])
        ], className="mb-4"),

        budget_panel,

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("总支出", className="card-title text-muted"),
                        html.H3(id='kpi-total', className="text-primary", style={'fontWeight': 'bold'}),
                    ])
                ], className="h-100")
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("消费笔数", className="card-title text-muted"),
                        html.H3(id='kpi-count', className="text-success", style={'fontWeight': 'bold'}),
                    ])
                ], className="h-100")
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("平均客单价", className="card-title text-muted"),
                        html.H3(id='kpi-avg', className="text-warning", style={'fontWeight': 'bold'}),
                    ])
                ], className="h-100")
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("异常笔数", className="card-title text-muted"),
                        html.H3(id='kpi-abnormal', className="text-danger", style={'fontWeight': 'bold'}),
                    ])
                ], className="h-100")
            ], width=3),
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-category-pie')
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-budget-progress')
                    ])
                ])
            ], width=6),
        ], className="mb-4"),

        dbc.Card([
            dbc.CardBody([
                dcc.Graph(id='chart-budget-comparison')
            ])
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-heatmap')
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-emotion-scatter')
                    ])
                ])
            ], width=6),
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-trend')
                    ])
                ])
            ], width=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-payment')
                    ])
                ])
            ], width=4),
        ], className="mb-4"),

        html.Div(id='abnormal-list-container', className="mb-4"),

        html.Div(id='overspend-cause-container', className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-cause-dist')
                    ])
                ])
            ], width=5),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(id='chart-simulation')
                    ])
                ])
            ], width=7),
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader("🎯 下月预算模拟器", className="bg-success text-white"),
            dbc.CardBody([
                html.Div(id='simulator-content', className="mb-4"),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("整体调整系数：", className="fw-bold"),
                        dcc.Slider(
                            id='sim-adjustment-factor',
                            min=0.5, max=1.5, step=0.05, value=1.0,
                            marks={0.5: '×0.5 节俭', 0.8: '×0.8 保守', 1.0: '×1.0 正常', 1.2: '×1.2 宽松', 1.5: '×1.5 大方'},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("下月是否节假日月：", className="fw-bold"),
                        dbc.Switch(
                            id='sim-holiday-switch',
                            label="启用节假日系数",
                            value=False,
                            className="mt-2"
                        ),
                    ], width=3),
                    dbc.Col([
                        dbc.Button("🔄 重新模拟", id='run-simulation-btn',
                                   color="success", className="w-100 mt-2"),
                    ], width=3),
                ], className="mt-4 pt-3 border-top"),
            ])
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("🔍 消费模式识别", className="bg-warning"),
                    dbc.CardBody(id='patterns-card')
                ])
            ], width=5),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("💰 预算建议", className="bg-success text-white"),
                    dbc.CardBody(id='budget-card')
                ])
            ], width=7),
        ], className="mb-4"),

        dbc.Card([
            dbc.CardHeader("📋 消费明细", className="bg-light"),
            dbc.CardBody([
                dash_table.DataTable(
                    id='data-table',
                    page_size=15,
                    style_table={'overflowX': 'auto'},
                    style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                    style_cell={'textAlign': 'left', 'padding': '8px'},
                    style_data_conditional=[
                        {'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'}
                    ]
                )
            ])
        ], className="mb-5"),

    ], fluid=True, style={'paddingBottom': '40px'})


app.layout = build_layout


@app.callback(
    Output('file-status', 'children'),
    Output('filter-months', 'options'),
    Output('filter-categories', 'options'),
    Output('filter-payments', 'options'),
    Output('filter-scenes', 'options'),
    Output('filter-goals', 'options'),
    Input('upload-data', 'contents'),
    Input('use-sample', 'n_clicks'),
    State('upload-data', 'filename'),
    prevent_initial_call=False
)
def on_data_change(contents, n_clicks, filename):
    global current_df, current_msg, current_budget_config, current_savings_goal
    trigger = ""
    if ctx.triggered:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger == 'upload-data' and contents:
        parsed_df, msg = parse_contents(contents, filename or '')
        current_msg = msg
        if parsed_df is not None and not parsed_df.empty:
            current_df = parsed_df
            current_budget_config = init_budget_from_history(current_df)
            total_b = sum(v['monthly_budget'] for v in current_budget_config.values())
            current_savings_goal = round(total_b * 0.15, -1)
    elif trigger == 'use-sample' or (trigger == '' and current_df is None):
        init_data()

    if current_df is None or current_df.empty:
        return current_msg, [], [], [], [], []

    try:
        months = [{'label': m, 'value': m} for m in sorted(current_df['月份'].unique(), reverse=True)]
        cats = [{'label': c, 'value': c} for c in sorted(current_df['类别'].unique())]
        pays = [{'label': p, 'value': p} for p in sorted(current_df['支付方式'].unique())]
        scenes = [{'label': s, 'value': s} for s in sorted(current_df['场景'].unique())]
        goals = [{'label': g, 'value': g} for g in sorted(current_df['消费目标'].unique())]
        return current_msg, months, cats, pays, scenes, goals
    except Exception:
        traceback.print_exc()
        return current_msg + " (处理异常)", [], [], [], [], []


@app.callback(
    Output('filter-months', 'value'),
    Output('filter-categories', 'value'),
    Output('filter-payments', 'value'),
    Output('filter-scenes', 'value'),
    Output('filter-goals', 'value'),
    Input('reset-filter', 'n_clicks'),
    prevent_initial_call=True
)
def reset_filters(_):
    return None, None, None, None, None


@app.callback(
    Output('total-budget-display', 'children'),
    Output('total-disposable-display', 'children'),
    Input({'type': 'budget-input', 'category': ALL, 'field': 'monthly_budget'}, 'value'),
    Input('savings-goal-input', 'value'),
    prevent_initial_call=False
)
def update_total_budget_display(budget_values, savings_val):
    try:
        total = 0.0
        for v in budget_values:
            if v is not None:
                total += float(v)
        sv = float(savings_val) if savings_val is not None else 0.0
        return f"¥{total:,.0f}", f"¥{total + sv:,.0f}"
    except Exception:
        return "¥0", "¥0"


def collect_budget_config_from_inputs(monthly_vals, flex_vals, necessity_vals, holiday_vals, savings_val):
    global current_budget_config, current_savings_goal
    try:
        cats_len = len(CATEGORIES)
        for i, cat in enumerate(CATEGORIES):
            if i < cats_len:
                current_budget_config[cat]['monthly_budget'] = float(monthly_vals[i]) if i < len(monthly_vals) and monthly_vals[i] is not None else 0.0
                current_budget_config[cat]['flex_range'] = float(flex_vals[i]) / 100.0 if i < len(flex_vals) and flex_vals[i] is not None else 0.15
                current_budget_config[cat]['necessity_weight'] = float(necessity_vals[i]) if i < len(necessity_vals) and necessity_vals[i] is not None else 0.7
                current_budget_config[cat]['holiday_coeff'] = float(holiday_vals[i]) if i < len(holiday_vals) and holiday_vals[i] is not None else 1.3
        current_savings_goal = float(savings_val) if savings_val is not None else 0.0
    except Exception:
        traceback.print_exc()


@app.callback(
    Output('kpi-total', 'children'),
    Output('kpi-count', 'children'),
    Output('kpi-avg', 'children'),
    Output('kpi-abnormal', 'children'),
    Output('chart-category-pie', 'figure'),
    Output('chart-budget-progress', 'figure'),
    Output('chart-budget-comparison', 'figure'),
    Output('chart-heatmap', 'figure'),
    Output('chart-emotion-scatter', 'figure'),
    Output('chart-trend', 'figure'),
    Output('chart-payment', 'figure'),
    Output('chart-cause-dist', 'figure'),
    Output('chart-simulation', 'figure'),
    Output('patterns-card', 'children'),
    Output('budget-card', 'children'),
    Output('abnormal-list-container', 'children'),
    Output('overspend-cause-container', 'children'),
    Output('simulator-content', 'children'),
    Output('data-table', 'data'),
    Output('data-table', 'columns'),

    Input('filter-months', 'value'),
    Input('filter-categories', 'value'),
    Input('filter-payments', 'value'),
    Input('filter-scenes', 'value'),
    Input('filter-goals', 'value'),

    Input('apply-budget-btn', 'n_clicks'),
    Input('reset-budget-btn', 'n_clicks'),
    Input('run-simulation-btn', 'n_clicks'),
    Input('sim-adjustment-factor', 'value'),
    Input('sim-holiday-switch', 'value'),

    State({'type': 'budget-input', 'category': ALL, 'field': 'monthly_budget'}, 'value'),
    State({'type': 'budget-input', 'category': ALL, 'field': 'flex_range'}, 'value'),
    State({'type': 'budget-slider', 'category': ALL, 'field': 'necessity_weight'}, 'value'),
    State({'type': 'budget-input', 'category': ALL, 'field': 'holiday_coeff'}, 'value'),
    State('savings-goal-input', 'value'),
    prevent_initial_call=False
)
def update_dashboard(
    months, categories, payments, scenes, goals,
    apply_btn, reset_btn, sim_btn, adj_factor, hol_switch,
    monthly_vals, flex_vals, necessity_vals, holiday_vals, savings_val
):
    global current_budget_config, current_savings_goal, current_df
    try:
        trigger = ""
        if ctx.triggered:
            trigger = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger == 'reset-budget-btn':
            current_budget_config = init_budget_from_history(current_df)
            total_b = sum(v['monthly_budget'] for v in current_budget_config.values())
            current_savings_goal = round(total_b * 0.15, -1)
        elif trigger in ['apply-budget-btn', 'run-simulation-btn', 'sim-adjustment-factor', 'sim-holiday-switch']:
            collect_budget_config_from_inputs(monthly_vals, flex_vals, necessity_vals, holiday_vals, savings_val)

        if current_df is None or current_df.empty:
            fig = empty_fig()
            no_data_div = html.Div("暂无数据")
            return "-", "-", "-", "-", fig, fig, fig, fig, fig, fig, fig, fig, fig, no_data_div, no_data_div, no_data_div, no_data_div, no_data_div, [], []

        df = filter_dataframe(current_df, months, categories, payments, scenes, goals)

        if df.empty:
            fig = empty_fig("筛选后无数据")
            no_data_div = html.Div("筛选后无数据")
            return "¥0", "0", "¥0", "0", fig, fig, fig, fig, fig, fig, fig, fig, fig, no_data_div, no_data_div, no_data_div, no_data_div, no_data_div, [], []

        total = float(df['金额'].sum())
        count = len(df)
        avg = float(df['金额'].mean())

        patterns = detect_patterns(df)
        budget_info = generate_budget_suggestion(df)

        budget_series = compute_monthly_budget_series(df, current_budget_config, current_savings_goal)
        abnormal_df = detect_abnormal_expenses(df, current_budget_config)
        causes = analyze_overspend_causes(abnormal_df, current_budget_config)

        sim_adj = adj_factor if adj_factor is not None else 1.0
        sim_hol = hol_switch if hol_switch is not None else False
        sim_result = simulate_next_month_budget(
            df, current_budget_config, current_savings_goal,
            adjustment_factor=sim_adj, holiday_next=sim_hol, patterns=patterns
        )

        abnormal_count = len(abnormal_df) if abnormal_df is not None else 0

        patterns_content = build_patterns_content(patterns)
        budget_content = build_budget_suggestion_content(budget_info)
        abnormal_list = build_abnormal_list_table(abnormal_df)
        cause_cards = build_overspend_cause_cards(causes)
        simulator_content = build_budget_simulator_content(sim_result)

        display_cols = ['日期', '金额', '类别', '支付方式', '情绪标签', '场景', '消费目标', '备注']
        table_df = df[display_cols].copy()
        table_df['日期'] = table_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
        table_df['金额'] = table_df['金额'].round(2)
        table_df = table_df.sort_values('日期', ascending=False)
        columns = [{'name': c, 'id': c} for c in display_cols]
        table_data = table_df.to_dict('records')

        return (
            f"¥{total:,.2f}",
            f"{count:,}",
            f"¥{avg:,.2f}",
            f"{abnormal_count}",
            make_category_pie(df),
            make_budget_progress(df, budget_info, current_budget_config),
            make_budget_comparison_chart(budget_series),
            make_heatmap(df),
            make_emotion_scatter(df),
            make_trend_chart(df),
            make_payment_chart(df),
            make_cause_distribution_chart(causes),
            make_simulation_chart(sim_result),
            patterns_content,
            budget_content,
            abnormal_list,
            cause_cards,
            simulator_content,
            table_data,
            columns
        )
    except Exception:
        traceback.print_exc()
        err_fig = empty_fig("内部错误")
        err_msg = html.Div([
            html.H5("发生错误", className="text-danger"),
            html.Pre(traceback.format_exc(), className="small")
        ])
        return "-", "-", "-", "-", err_fig, err_fig, err_fig, err_fig, err_fig, err_fig, err_fig, err_fig, err_fig, err_msg, err_msg, err_msg, err_msg, err_msg, [], []


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=9201)
