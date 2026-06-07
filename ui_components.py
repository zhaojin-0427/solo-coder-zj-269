import traceback

import pandas as pd
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc

from data_parser import CATEGORIES


def build_budget_config_panel(budget_config, savings_goal=0):
    try:
        category_rows = []
        for cat in CATEGORIES:
            cfg = budget_config.get(cat, {})
            monthly = float(cfg.get('monthly_budget', 0))
            flex = float(cfg.get('flex_range', 0.15)) * 100
            necessity = float(cfg.get('necessity_weight', 0.7))
            holiday = float(cfg.get('holiday_coeff', 1.3))

            category_rows.append(
                dbc.Row([
                    dbc.Col(html.Strong(cat, className="align-middle"), width=2),
                    dbc.Col([
                        html.Label("月预算(¥)", className="small text-muted mb-0"),
                        dbc.Input(
                            id={'type': 'budget-input', 'category': cat, 'field': 'monthly_budget'},
                            type='number', min=0, step=10, value=monthly, size="sm",
                            style={'width': '100%'}
                        ),
                    ], width=3),
                    dbc.Col([
                        html.Label("弹性区间(%)", className="small text-muted mb-0"),
                        dbc.Input(
                            id={'type': 'budget-input', 'category': cat, 'field': 'flex_range'},
                            type='number', min=0, max=100, step=1, value=flex, size="sm",
                            style={'width': '100%'}
                        ),
                    ], width=2),
                    dbc.Col([
                        html.Label("必要权重", className="small text-muted mb-0"),
                        dcc.Slider(
                            id={'type': 'budget-slider', 'category': cat, 'field': 'necessity_weight'},
                            min=0.1, max=1.0, step=0.05, value=necessity,
                            marks={0.1: '低', 0.5: '中', 1.0: '高'},
                            tooltip={"placement": "bottom", "always_visible": False}
                        ),
                    ], width=3),
                    dbc.Col([
                        html.Label("节假日系数", className="small text-muted mb-0"),
                        dbc.Input(
                            id={'type': 'budget-input', 'category': cat, 'field': 'holiday_coeff'},
                            type='number', min=1.0, max=3.0, step=0.1, value=holiday, size="sm",
                            style={'width': '100%'}
                        ),
                    ], width=2),
                ], className="mb-2 align-items-center")
            )

        total_budget = sum(v.get('monthly_budget', 0) for v in budget_config.values())

        panel = dbc.Card([
            dbc.CardHeader("⚙️ 预算配置中心", className="bg-primary text-white"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("储蓄目标 (¥/月)", className="fw-bold"),
                        dbc.Input(
                            id='savings-goal-input',
                            type='number', min=0, step=50, value=savings_goal, size="lg",
                            style={'width': '100%'}
                        ),
                    ], width=4),
                    dbc.Col([
                        html.Label("总预算 (¥/月)", className="fw-bold text-success"),
                        html.H4(id='total-budget-display',
                                children=f"¥{total_budget:,.0f}",
                                className="text-success fw-bold mb-0"),
                    ], width=4),
                    dbc.Col([
                        html.Label("总可支配 (预算+储蓄)", className="fw-bold text-info"),
                        html.H4(id='total-disposable-display',
                                children=f"¥{total_budget + savings_goal:,.0f}",
                                className="text-info fw-bold mb-0"),
                    ], width=4),
                ], className="mb-3 pb-3 border-bottom"),
                dbc.Row([
                    dbc.Col(html.Strong("类别", className="text-muted small"), width=2),
                    dbc.Col(html.Strong("月预算", className="text-muted small"), width=3),
                    dbc.Col(html.Strong("弹性%", className="text-muted small"), width=2),
                    dbc.Col(html.Strong("必要程度", className="text-muted small"), width=3),
                    dbc.Col(html.Strong("节假日系数", className="text-muted small"), width=2),
                ], className="mb-2"),
                html.Div(category_rows, id='budget-category-rows'),
                dbc.Row([
                    dbc.Col([
                        dbc.Button("💾 应用预算配置", id='apply-budget-btn',
                                   color="success", className="mt-3 w-100", size="md"),
                    ], width=6),
                    dbc.Col([
                        dbc.Button("🔄 重置为历史均值", id='reset-budget-btn',
                                   color="secondary", className="mt-3 w-100", size="md"),
                    ], width=6),
                ]),
            ])
        ], className="mb-4")
        return panel
    except Exception:
        traceback.print_exc()
        return dbc.Card(dbc.CardBody("预算配置面板加载失败"), className="mb-4")


def build_abnormal_list_table(abnormal_df):
    try:
        if abnormal_df is None or abnormal_df.empty:
            return dbc.Card([
                dbc.CardHeader("⚠️ 异常消费清单", className="bg-warning text-dark"),
                dbc.CardBody(html.P("暂无异常消费记录，消费表现良好！", className="text-success mb-0"))
            ], className="mb-4")

        display_df = abnormal_df.copy()
        if '日期' in display_df.columns:
            display_df['日期'] = pd.to_datetime(display_df['日期']).dt.strftime('%Y-%m-%d %H:%M')
        display_cols = ['日期', '金额', '类别', '支付方式', '情绪标签', '场景', '消费目标', '超支原因', '备注']
        for c in display_cols:
            if c not in display_df.columns:
                display_df[c] = ''
        display_df = display_df[display_cols]
        if '金额' in display_df.columns:
            display_df['金额'] = display_df['金额'].round(2)

        style_data_conditional = [
            {'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'},
            {
                'if': {
                    'filter_query': '{严重程度} >= 2' if '严重程度' in abnormal_df.columns else None,
                },
                'backgroundColor': '#FFE4E1',
                'color': '#8B0000'
            },
            {
                'if': {
                    'filter_query': '{情绪标签} contains "冲动" || {情绪标签} contains "后悔"'
                },
                'fontWeight': 'bold'
            }
        ]

        return dbc.Card([
            dbc.CardHeader([
                html.Span("⚠️ 异常消费清单", className="me-2"),
                dbc.Badge(f"{len(abnormal_df)} 条异常", color="danger", className="ms-2")
            ], className="bg-warning text-dark"),
            dbc.CardBody([
                dbc.Alert(
                    "🔴 红色高亮=严重异常（多重原因），粗体=情绪驱动消费",
                    color="light", className="small mb-2"
                ),
                dash_table.DataTable(
                    id='abnormal-table',
                    data=display_df.to_dict('records'),
                    columns=[{'name': c, 'id': c} for c in display_cols],
                    page_size=10,
                    style_table={'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'},
                    style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                    style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '12px'},
                    style_data_conditional=style_data_conditional,
                    sort_action='native',
                    filter_action='native',
                )
            ])
        ], className="mb-4")
    except Exception:
        traceback.print_exc()
        return dbc.Card([
            dbc.CardHeader("⚠️ 异常消费清单", className="bg-warning text-dark"),
            dbc.CardBody(html.P("清单加载出错", className="text-danger mb-0"))
        ], className="mb-4")


def build_overspend_cause_cards(causes):
    try:
        cause_info = {
            '结构性超支': {
                'icon': '🏗️',
                'color': 'danger',
                'desc': '必要支出长期超过预算，需重新评估预算基线',
                'badge': '结构性'
            },
            '情绪驱动超支': {
                'icon': '😤',
                'color': 'warning',
                'desc': '冲动/后悔/焦虑情绪引发的非理性消费',
                'badge': '情绪性'
            },
            '节假日波动': {
                'icon': '🎉',
                'color': 'info',
                'desc': '节假日/旅行/聚餐等季节性消费波动',
                'badge': '季节性'
            },
            '一次性大额支出': {
                'icon': '💎',
                'color': 'secondary',
                'desc': '单笔大额支出（家电/数码/医疗等）',
                'badge': '偶发性'
            }
        }

        cards = []
        total_amount = 0
        for cause_name, cause_data in causes.items():
            info = cause_info.get(cause_name, {'icon': '📊', 'color': 'secondary', 'desc': '', 'badge': cause_name})
            amount = cause_data.get('amount', 0)
            count = cause_data.get('count', 0)
            categories = cause_data.get('categories', {})
            total_amount += amount

            top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
            cat_text = '、'.join([f"{c} ¥{a:.0f}" for c, a in top_cats]) if top_cats else '无明细'

            has_data = amount > 0 or count > 0

            card = dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span(info['icon'], className="me-2"),
                        html.Strong(cause_name),
                        dbc.Badge(info['badge'], color=info['color'], className="ms-2", pill=True),
                        dbc.Badge(f"{count}次", color="light", className="ms-auto text-dark")
                    ], className=f"bg-{'light' if not has_data else info['color']} text-{'dark' if not has_data else 'white'}"),
                    dbc.CardBody([
                        html.H4(
                            f"¥{amount:,.0f}",
                            className=f"text-{info['color'] if has_data else 'muted'} fw-bold mb-2"
                        ),
                        html.P(info['desc'], className="small text-muted mb-2"),
                        html.Div([
                            html.Span("主要类别：", className="small text-muted"),
                            html.Span(cat_text, className="small fw-bold")
                        ])
                    ])
                ], className="h-100 shadow-sm" if has_data else "h-100 opacity-75")
            ], width=3)
            cards.append(card)

        header = dbc.Row([
            dbc.Col([
                html.H5("📊 超支归因分析", className="fw-bold mb-1"),
                html.P([
                    "累计异常金额 ",
                    html.Strong(f"¥{total_amount:,.0f}", className="text-danger"),
                    "，按四类原因拆解如下"
                ], className="text-muted small mb-0")
            ])
        ], className="mb-3")

        return dbc.Card([
            dbc.CardBody([
                header,
                dbc.Row(cards)
            ])
        ], className="mb-4")
    except Exception:
        traceback.print_exc()
        return dbc.Card(
            dbc.CardBody("归因卡片加载失败"),
            className="mb-4"
        )


def build_budget_simulator_content(simulation_result):
    try:
        if not simulation_result:
            return html.Div([
                html.P("请先配置预算参数", className="text-muted mb-0")
            ])

        totals = simulation_result.get('_totals', {})
        suggestions = simulation_result.get('_suggestions', [])

        table_rows = []
        for cat in CATEGORIES:
            if cat in simulation_result:
                info = simulation_result[cat]
                table_rows.append(html.Tr([
                    html.Td(html.Strong(cat)),
                    html.Td(f"¥{info['base_budget']:,.0f}"),
                    html.Td(f"¥{info['flex_lower']:,.0f} ~ ¥{info['flex_upper']:,.0f}"),
                    html.Td(f"{info['flex_range_pct']:.0f}%"),
                    html.Td([
                        dbc.Progress(
                            value=info['necessity_weight'] * 100,
                            color='success' if info['necessity_weight'] >= 0.8 else ('warning' if info['necessity_weight'] >= 0.5 else 'danger'),
                            style={'height': '10px'},
                            label=f"{info['necessity_weight']:.0%}"
                        )
                    ]),
                    html.Td(f"×{info['holiday_coeff']:.1f}"),
                ]))

        suggestion_items = [
            html.Li(s, className="mb-1") for s in suggestions
        ]

        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Label("建议总预算", className="small text-muted mb-0"),
                            html.H3(f"¥{totals.get('total_budget', 0):,.0f}",
                                    className="text-success fw-bold mb-0"),
                        ])
                    ], className="text-center border-success"),
                ], width=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Label("储蓄目标", className="small text-muted mb-0"),
                            html.H3(f"¥{totals.get('savings_goal', 0):,.0f}",
                                    className="text-info fw-bold mb-0"),
                        ])
                    ], className="text-center border-info"),
                ], width=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Label("合计可支配", className="small text-muted mb-0"),
                            html.H3(f"¥{totals.get('total_with_savings', 0):,.0f}",
                                    className="text-primary fw-bold mb-0"),
                        ])
                    ], className="text-center border-primary"),
                ], width=4),
            ], className="mb-4"),

            dbc.Row([
                dbc.Col([
                    html.Label("📋 预算明细（含弹性区间）", className="fw-bold mb-2"),
                    dbc.Table([
                        html.Thead(html.Tr([
                            html.Th("类别"),
                            html.Th("计划预算"),
                            html.Th("弹性区间"),
                            html.Th("弹性%"),
                            html.Th("必要度"),
                            html.Th("节假日"),
                        ])),
                        html.Tbody(table_rows)
                    ], bordered=True, hover=True, size="sm", className="mb-0"),
                ], width=7),
                dbc.Col([
                    html.Label("💡 智能建议", className="fw-bold mb-2"),
                    html.Ul(suggestion_items, className="small", style={'paddingLeft': '18px'})
                ], width=5),
            ]),
        ])
    except Exception:
        traceback.print_exc()
        return html.Div([html.P("模拟器加载失败", className="text-danger mb-0")])


def build_patterns_content(patterns):
    try:
        pattern_items = []
        for key, info in patterns.items():
            if info.get('detected'):
                if info.get('severity') == '高':
                    badge_color = 'danger'
                elif info.get('severity') == '中':
                    badge_color = 'warning'
                else:
                    badge_color = 'success'
            else:
                badge_color = 'secondary'
            badge_text = info.get('severity', '无') if info.get('detected') else '正常'
            pattern_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong(info.get('label', key)),
                        dbc.Badge(badge_text, color=badge_color, className="ms-2")
                    ]),
                    html.Small(info.get('detail', ''), className="text-muted d-block mt-1")
                ], className="mb-2")
            )
        return dbc.ListGroup(pattern_items, className="list-group-flush")
    except Exception:
        traceback.print_exc()
        return html.Div("模式识别加载失败")


def build_budget_suggestion_content(budget_info):
    try:
        if not budget_info:
            return html.Div("暂无足够数据生成建议")

        alloc_items = []
        total_b = budget_info.get('total_budget', 0)
        for cat, amt in budget_info.get('allocation', {}).items():
            if amt and amt > 0:
                pct = amt / total_b * 100 if total_b > 0 else 0
                alloc_items.append(
                    dbc.ListGroupItem([
                        html.Div([
                            html.Strong(f"{cat}: ¥{amt:.0f}"),
                            dbc.Progress(value=pct, color="success", className="mt-2", style={'height': '8px'})
                        ])
                    ])
                )
        suggestion_items = [
            html.Li(s, className="mb-1") for s in budget_info.get('suggestions', [])
        ]
        return dbc.Row([
            dbc.Col([
                html.H6("预算概览", className="text-success"),
                html.P("建议总预算: ", className="mb-1"),
                html.H4(f"¥{budget_info.get('total_budget', 0):.0f}", className="text-success fw-bold"),
                html.P(f"储蓄目标: ¥{budget_info.get('savings_goal', 0):.0f}", className="text-info"),
                html.P(f"上月支出: ¥{budget_info.get('last_month', 0):.0f}", className="text-muted small mb-1"),
                html.P(f"历史月均: ¥{budget_info.get('avg_monthly', 0):.0f}", className="text-muted small mb-0"),
                html.Hr(),
                html.H6("预算分配", className="text-success"),
                dbc.ListGroup(alloc_items, className="list-group-flush small")
            ], width=5),
            dbc.Col([
                html.H6("理财建议", className="text-success"),
                html.Ul(suggestion_items, className="small", style={'paddingLeft': '18px'})
            ], width=7)
        ])
    except Exception:
        traceback.print_exc()
        return html.Div("建议加载失败")
