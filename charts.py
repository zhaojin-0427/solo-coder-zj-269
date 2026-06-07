import traceback

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_parser import CATEGORIES


def empty_fig(title="暂无数据"):
    fig = go.Figure()
    fig.update_layout(title=title, height=300, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def make_category_pie(df):
    if df is None or df.empty:
        return empty_fig()
    try:
        cat_sum = df.groupby('类别')['金额'].sum().reset_index()
        cat_sum = cat_sum.sort_values('金额', ascending=False)
        colors = px.colors.qualitative.Pastel
        fig = go.Figure(data=[go.Pie(
            labels=cat_sum['类别'],
            values=cat_sum['金额'],
            hole=0.4,
            marker=dict(colors=colors[:len(cat_sum)]),
            textinfo='label+percent',
            textposition='outside',
        )])
        fig.update_layout(
            title="支出类别分布",
            height=420,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.1)
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_budget_progress(df, budget_info, budget_config=None):
    if df is None or df.empty:
        return empty_fig()
    try:
        monthly_sum = df.groupby('月份')['金额'].sum()
        if len(monthly_sum) == 0:
            return empty_fig()

        if budget_config:
            current_month = str(monthly_sum.index[-1])
            current_month_data = df[df['月份'] == current_month]
            cats = []
            spent_vals = []
            budget_vals = []
            flex_upper_vals = []
            for cat in CATEGORIES:
                cat_spent = float(current_month_data[current_month_data['类别'] == cat]['金额'].sum())
                cfg = budget_config.get(cat, {})
                cat_budget = float(cfg.get('monthly_budget', 0))
                cat_flex = float(cfg.get('flex_range', 0.15))
                if cat_budget > 0 or cat_spent > 0:
                    cats.append(cat)
                    spent_vals.append(round(cat_spent, 2))
                    budget_vals.append(round(cat_budget, 2))
                    flex_upper_vals.append(round(cat_budget * (1 + cat_flex), 2))

            if cats:
                pcts = []
                texts = []
                colors = []
                for s, b, f in zip(spent_vals, budget_vals, flex_upper_vals):
                    if b > 0:
                        pct = min(s / b * 100, 150)
                        pcts.append(pct)
                        texts.append(f"{s}/{b}<br>{s/b*100:.0f}%")
                        if s > f:
                            colors.append('#d62728')
                        elif s > b:
                            colors.append('#ff7f0e')
                        else:
                            colors.append('#2ca02c')
                    else:
                        pcts.append(0)
                        texts.append(f"{s}")
                        colors.append('#1f77b4')

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=cats, y=pcts,
                    marker_color=colors,
                    text=texts,
                    textposition='auto',
                    name='预算执行率',
                    hovertemplate='%{x}<br>执行率: %{y:.1f}%<extra></extra>'
                ))
                fig.add_hline(y=100, line_dash="dash", line_color="orange", annotation_text="预算线", annotation_position="top left")
                fig.add_hline(y=115, line_dash="dot", line_color="red", annotation_text="弹性上限", annotation_position="top right")
                fig.update_layout(
                    title=f"{current_month} 各类别预算执行进度",
                    yaxis_title="执行率 (%)",
                    height=380,
                    margin=dict(l=40, r=20, t=50, b=40),
                    showlegend=False
                )
                return fig

        if budget_info and budget_info.get('allocation'):
            current_month = str(monthly_sum.index[-1])
            current_month_data = df[df['月份'] == current_month]
            cats = []
            spent_vals = []
            budget_vals = []
            for cat in CATEGORIES:
                cat_spent = float(current_month_data[current_month_data['类别'] == cat]['金额'].sum())
                cat_budget = float(budget_info['allocation'].get(cat, 0))
                if cat_budget > 0 or cat_spent > 0:
                    cats.append(cat)
                    spent_vals.append(round(cat_spent, 2))
                    budget_vals.append(round(cat_budget, 2))

            if cats:
                pcts = []
                texts = []
                colors = []
                for s, b in zip(spent_vals, budget_vals):
                    if b > 0:
                        pct = min(s / b * 100, 150)
                        pcts.append(pct)
                        texts.append(f"{s}/{b}<br>{s/b*100:.0f}%")
                        if s > b:
                            colors.append('#d62728')
                        elif s > b * 0.8:
                            colors.append('#ff7f0e')
                        else:
                            colors.append('#2ca02c')
                    else:
                        pcts.append(0)
                        texts.append(f"{s}")
                        colors.append('#1f77b4')

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=cats, y=pcts,
                    marker_color=colors,
                    text=texts,
                    textposition='auto',
                    name='预算执行率'
                ))
                fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="预算线")
                fig.update_layout(
                    title=f"{current_month} 各类别预算执行进度",
                    yaxis_title="执行率 (%)",
                    height=380,
                    margin=dict(l=40, r=20, t=50, b=40),
                    showlegend=False
                )
                return fig

        fig = go.Figure(go.Bar(
            x=list(monthly_sum.index), y=list(monthly_sum.values),
            marker_color='#636EFA',
            text=[f"¥{v:.0f}" for v in monthly_sum.values],
            textposition='outside'
        ))
        fig.update_layout(
            title="月度总支出",
            yaxis_title="金额 (¥)",
            height=380,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_heatmap(df):
    if df is None or df.empty:
        return empty_fig()
    try:
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        hour_bins = [0, 6, 12, 14, 18, 22, 24]
        hour_labels = ['凌晨(0-6)', '上午(6-12)', '午间(12-14)', '下午(14-18)', '晚间(18-22)', '深夜(22-24)']

        df_copy = df.copy()
        df_copy['时段'] = pd.cut(df_copy['小时'], bins=hour_bins, labels=hour_labels, include_lowest=True, right=False)
        heat = df_copy.groupby(['星期', '时段'])['金额'].sum().unstack(fill_value=0)
        for d in day_order:
            if d not in heat.index:
                heat.loc[d] = 0
        heat = heat.reindex(day_order)
        heat.index = day_cn
        for hl in hour_labels:
            if hl not in heat.columns:
                heat[hl] = 0
        heat = heat[hour_labels]

        fig = go.Figure(data=go.Heatmap(
            z=heat.values,
            x=list(heat.columns),
            y=list(heat.index),
            colorscale='YlOrRd',
            text=[[f"¥{v:.0f}" for v in row] for row in heat.values],
            texttemplate="%{text}",
            hoverongaps=False
        ))
        fig.update_layout(
            title="消费时段热力图",
            height=380,
            margin=dict(l=60, r=20, t=50, b=40),
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_emotion_scatter(df):
    if df is None or df.empty:
        return empty_fig()
    try:
        fig = px.scatter(
            df, x='日期', y='金额',
            color='情绪标签',
            size='金额',
            size_max=20,
            hover_data=['类别', '支付方式', '场景', '备注'],
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(
            title="情绪消费散点图",
            xaxis_title="日期",
            yaxis_title="金额 (¥)",
            height=420,
            margin=dict(l=40, r=20, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2)
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_trend_chart(df):
    if df is None or df.empty:
        return empty_fig()
    try:
        monthly_trend = df.groupby('月份').agg(
            总支出=('金额', 'sum'),
            消费次数=('金额', 'count'),
            平均客单价=('金额', 'mean')
        ).reset_index()

        if monthly_trend.empty:
            return empty_fig()

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(
            x=list(monthly_trend['月份']), y=list(monthly_trend['总支出']),
            name='总支出', marker_color='#636EFA',
            text=[f"¥{v:.0f}" for v in monthly_trend['总支出']],
            textposition='outside'
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=list(monthly_trend['月份']), y=list(monthly_trend['平均客单价']),
            name='平均客单价', mode='lines+markers',
            line=dict(color='#EF553B', width=3),
            marker=dict(size=8)
        ), secondary_y=True)
        fig.add_trace(go.Scatter(
            x=list(monthly_trend['月份']), y=list(monthly_trend['消费次数']),
            name='消费次数', mode='lines+markers',
            line=dict(color='#00CC96', width=2, dash='dot'),
            marker=dict(size=6)
        ), secondary_y=True)

        if len(monthly_trend) >= 2:
            x_arr = np.arange(len(monthly_trend))
            y_arr = monthly_trend['总支出'].values.astype(float)
            z = np.polyfit(x_arr, y_arr, 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=list(monthly_trend['月份']),
                y=list(p(x_arr)),
                name=f"趋势线 (斜率: {z[0]:.0f})",
                line=dict(color='gray', dash='dash', width=2),
                mode='lines'
            ), secondary_y=False)

        fig.update_layout(
            title="月度消费趋势分析",
            height=450,
            margin=dict(l=40, r=40, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            barmode='group'
        )
        fig.update_yaxes(title_text="总支出 (¥)", secondary_y=False)
        fig.update_yaxes(title_text="客单价/次数", secondary_y=True)
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_payment_chart(df):
    if df is None or df.empty:
        return empty_fig()
    try:
        pay = df.groupby('支付方式')['金额'].sum().reset_index().sort_values('金额', ascending=True)
        fig = go.Figure(go.Bar(
            x=list(pay['金额']), y=list(pay['支付方式']),
            orientation='h',
            marker_color=px.colors.qualitative.Pastel1[:len(pay)],
            text=[f"¥{v:.0f}" for v in pay['金额']],
            textposition='outside'
        ))
        fig.update_layout(
            title="支付方式分布",
            xaxis_title="金额 (¥)",
            height=350,
            margin=dict(l=80, r=40, t=50, b=40),
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("图表生成失败")


def make_budget_comparison_chart(budget_series_df):
    if budget_series_df is None or budget_series_df.empty:
        return empty_fig()
    try:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=budget_series_df['月份'],
            y=budget_series_df['实际支出'],
            mode='lines+markers',
            name='实际支出',
            line=dict(color='#636EFA', width=3),
            marker=dict(size=8, symbol='circle'),
            fill=None
        ))

        fig.add_trace(go.Scatter(
            x=budget_series_df['月份'],
            y=budget_series_df['计划预算'],
            mode='lines+markers',
            name='计划预算',
            line=dict(color='#2ca02c', width=2, dash='dash'),
            marker=dict(size=6, symbol='square')
        ))

        fig.add_trace(go.Scatter(
            x=budget_series_df['月份'],
            y=budget_series_df['调整后预算'],
            mode='lines',
            name='调整后预算',
            line=dict(color='#ff7f0e', width=2, dash='dot'),
            fill=None
        ))

        for i, row in budget_series_df.iterrows():
            if row['实际支出'] > row['调整后预算']:
                fig.add_annotation(
                    x=row['月份'],
                    y=row['实际支出'],
                    text=f"超支 ¥{row['超支金额']:.0f}",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor='#d62728',
                    ax=0,
                    ay=-40,
                    font=dict(color='#d62728', size=10)
                )

        holiday_months = budget_series_df[budget_series_df['是否节假日月']]
        if not holiday_months.empty:
            for _, hm in holiday_months.iterrows():
                fig.add_vrect(
                    x0=hm['月份'], x1=hm['月份'],
                    fillcolor="#FFE4B5", opacity=0.3,
                    layer="below", line_width=0,
                    annotation_text="节假日月",
                    annotation_position="top"
                )

        fig.update_layout(
            title="实际支出 vs 计划预算 vs 调整后预算（多序列时序对比）",
            xaxis_title="月份",
            yaxis_title="金额 (¥)",
            height=450,
            margin=dict(l=50, r=30, t=60, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=-0.18),
            hovermode="x unified"
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("预算对比图生成失败")


def make_cause_distribution_chart(causes):
    try:
        labels = []
        values = []
        for k, v in causes.items():
            if v['amount'] > 0:
                labels.append(k)
                values.append(v['amount'])

        if not values:
            return empty_fig("暂无超支归因数据")

        colors = ['#d62728', '#ff7f0e', '#ffbf00', '#9467bd']

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            marker=dict(colors=colors[:len(labels)]),
            textinfo='label+percent+value',
            textposition='outside',
            texttemplate='%{label}<br>¥%{value:.0f} (%{percent})',
        )])
        fig.update_layout(
            title="四类超支原因金额分布",
            height=380,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.1)
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("归因分布图生成失败")


def make_simulation_chart(simulation_result):
    if not simulation_result:
        return empty_fig()
    try:
        cats = []
        budgets = []
        flex_lower = []
        flex_upper = []
        for cat in CATEGORIES:
            if cat in simulation_result:
                info = simulation_result[cat]
                cats.append(cat)
                budgets.append(info['base_budget'])
                flex_lower.append(info['flex_lower'])
                flex_upper.append(info['flex_upper'])

        if not cats:
            return empty_fig()

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=cats,
            y=[u - l for u, l in zip(flex_upper, flex_lower)],
            base=flex_lower,
            name='弹性区间',
            marker_color='rgba(255, 191, 0, 0.4)',
            hovertemplate='弹性区间<br>下限: ¥%{base:.0f}<br>上限: ¥%{y:.0f}<extra></extra>'
        ))

        fig.add_trace(go.Scatter(
            x=cats,
            y=budgets,
            mode='markers',
            name='计划预算',
            marker=dict(color='#2ca02c', size=12, symbol='diamond'),
            hovertemplate='%{x}<br>预算: ¥%{y:.0f}<extra></extra>'
        ))

        for i, cat in enumerate(cats):
            info = simulation_result[cat]
            fig.add_annotation(
                x=cat,
                y=budgets[i],
                text=f"必要度 {info['necessity_weight']:.0%}",
                showarrow=False,
                yshift=20,
                font=dict(size=9, color='#555')
            )

        fig.update_layout(
            title="下月预算模拟（含弹性区间）",
            xaxis_title="消费类别",
            yaxis_title="金额 (¥)",
            height=420,
            margin=dict(l=50, r=20, t=60, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=-0.18),
            barmode='stack'
        )
        return fig
    except Exception:
        traceback.print_exc()
        return empty_fig("模拟图生成失败")
