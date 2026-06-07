import base64
import io
import datetime
import re
import traceback

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.MINTY])
app.title = "手账消费记录与月度预算分析台"
server = app.server

CATEGORIES = ['餐饮', '购物', '交通', '娱乐', '居家', '医疗', '教育', '旅行', '其他']
PAYMENT_METHODS = ['微信', '支付宝', '信用卡', '现金', '银行卡', '花呗', '其他']
EMOTIONS = ['开心', '平静', '焦虑', '冲动', '后悔', '满足', '疲惫']
SCENES = ['日常', '聚餐', '通勤', '约会', '购物日', '节日', '旅行', '加班']
GOALS = ['刚需', '改善生活', '社交', '兴趣爱好', '应急', '储蓄', '其他']

current_df = None
current_msg = ""


def generate_sample_data():
    try:
        np.random.seed(42)
        n = 500
        dates = pd.date_range(start='2025-01-01', end='2026-05-31', periods=n)
        amounts = np.abs(np.random.gamma(2, 50, n)).round(2)
        categories = np.random.choice(CATEGORIES, n, p=[0.25, 0.2, 0.12, 0.1, 0.1, 0.05, 0.08, 0.05, 0.05])
        payments = np.random.choice(PAYMENT_METHODS, n, p=[0.35, 0.3, 0.15, 0.05, 0.08, 0.05, 0.02])
        emotions = np.random.choice(EMOTIONS, n, p=[0.2, 0.3, 0.08, 0.15, 0.07, 0.12, 0.08])
        scenes_list = np.random.choice(SCENES, n)
        goals_list = np.random.choice(GOALS, n, p=[0.4, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05])

        for i in range(n):
            h = dates[i].hour
            if categories[i] == '餐饮' and np.random.random() < 0.3:
                amounts[i] = round(float(np.random.uniform(10, 35)), 2)
                if h >= 22 or h <= 2:
                    emotions[i] = np.random.choice(['冲动', '后悔'])
            if categories[i] == '购物' and (h >= 22 or h <= 1):
                emotions[i] = np.random.choice(['冲动', '后悔', '开心'])
                amounts[i] = round(amounts[i] * 1.5, 2)

        df = pd.DataFrame({
            '日期': dates,
            '金额': amounts,
            '类别': categories,
            '支付方式': payments,
            '情绪标签': emotions,
            '场景': scenes_list,
            '消费目标': goals_list,
            '备注': [f'消费记录_{i}' for i in range(n)]
        })
        df['日期'] = pd.to_datetime(df['日期'])
        df['月份'] = df['日期'].dt.strftime('%Y-%m')
        df['小时'] = df['日期'].dt.hour
        df['星期'] = df['日期'].dt.day_name()
        return df
    except Exception:
        traceback.print_exc()
        return pd.DataFrame()


def init_data():
    global current_df, current_msg
    current_df = generate_sample_data()
    current_msg = "已加载示例数据（500条）"


init_data()


def parse_contents(contents, filename):
    global current_df, current_msg
    if contents is None:
        current_msg = "未上传文件"
        return
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        if 'csv' in filename.lower():
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename.lower():
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            current_msg = "不支持的文件格式，请使用 CSV 或 Excel"
            return

        col_map = {}
        for col in df.columns:
            low = str(col).lower()
            if any(k in low for k in ['date', '日期', '时间', 'time']):
                col_map[col] = '日期'
            elif any(k in low for k in ['amount', '金额', '价格', '花费', '支出']):
                col_map[col] = '金额'
            elif any(k in low for k in ['category', '类别', '分类', '类型']):
                col_map[col] = '类别'
            elif any(k in low for k in ['payment', '支付', '付款']):
                col_map[col] = '支付方式'
            elif any(k in low for k in ['emotion', '情绪', '心情']):
                col_map[col] = '情绪标签'
            elif any(k in low for k in ['scene', '场景']):
                col_map[col] = '场景'
            elif any(k in low for k in ['goal', '目标']):
                col_map[col] = '消费目标'
            elif any(k in low for k in ['note', '备注', '说明', '描述']):
                col_map[col] = '备注'

        df = df.rename(columns=col_map)
        if '日期' not in df.columns or '金额' not in df.columns:
            current_msg = "CSV 需包含 日期/时间 和 金额/价格 列"
            return

        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        df = df.dropna(subset=['日期'])
        df['金额'] = pd.to_numeric(df['金额'], errors='coerce').fillna(0)
        df = df[df['金额'] > 0]

        if '类别' not in df.columns:
            df['类别'] = '其他'
        if '支付方式' not in df.columns:
            df['支付方式'] = '其他'
        if '情绪标签' not in df.columns:
            df['情绪标签'] = '平静'
        if '场景' not in df.columns:
            df['场景'] = '日常'
        if '消费目标' not in df.columns:
            df['消费目标'] = '刚需'
        if '备注' not in df.columns:
            df['备注'] = ''

        df['月份'] = df['日期'].dt.strftime('%Y-%m')
        df['小时'] = df['日期'].dt.hour
        df['星期'] = df['日期'].dt.day_name()

        current_df = df.reset_index(drop=True)
        current_msg = f"成功加载 {len(current_df)} 条记录"
    except Exception as e:
        traceback.print_exc()
        current_msg = f"解析错误: {str(e)}"


def detect_patterns(df):
    patterns = {}
    if df.empty:
        return patterns

    try:
        milk_tea_mask = (df['类别'] == '餐饮') & (df['金额'] >= 8) & (df['金额'] <= 45)
        note_mask = df['备注'].astype(str).str.contains(r'奶茶|咖啡|星巴克|瑞幸|喜茶|奈雪', case=False, na=False)
        milk_tea = df[milk_tea_mask | note_mask]
        if len(milk_tea) > 0:
            monthly = milk_tea.groupby('月份').size()
            avg_monthly = float(monthly.mean()) if len(monthly) > 0 else 0
            patterns['奶茶依赖'] = {
                'label': '奶茶依赖 🧋',
                'detected': avg_monthly >= 6,
                'detail': f"月均 {avg_monthly:.1f} 杯，累计消费 ¥{milk_tea['金额'].sum():.2f}",
                'severity': '高' if avg_monthly >= 12 else ('中' if avg_monthly >= 8 else '低')
            }
        else:
            patterns['奶茶依赖'] = {'label': '奶茶依赖 🧋', 'detected': False, 'detail': '暂无相关消费', 'severity': '无'}
    except Exception:
        patterns['奶茶依赖'] = {'label': '奶茶依赖 🧋', 'detected': False, 'detail': '分析异常', 'severity': '无'}

    try:
        late_night = df[(df['小时'] >= 22) | (df['小时'] <= 2)]
        if len(late_night) > 0:
            pct = len(late_night) / len(df) * 100
            patterns['深夜购物'] = {
                'label': '深夜购物 🌙',
                'detected': pct >= 10,
                'detail': f"深夜时段消费 {len(late_night)} 次，占比 {pct:.1f}%，金额 ¥{late_night['金额'].sum():.2f}",
                'severity': '高' if pct >= 25 else ('中' if pct >= 15 else '低')
            }
        else:
            patterns['深夜购物'] = {'label': '深夜购物 🌙', 'detected': False, 'detail': '暂无深夜消费', 'severity': '无'}
    except Exception:
        patterns['深夜购物'] = {'label': '深夜购物 🌙', 'detected': False, 'detail': '分析异常', 'severity': '无'}

    try:
        bulk_keywords = r'囤|批发|一箱|一打|套装|组合|大包装|多件|打折|促销|满减'
        bulk_mask = df['备注'].astype(str).str.contains(bulk_keywords, case=False, na=False)
        bulk = df[bulk_mask]
        if len(bulk) > 0:
            patterns['囤货倾向'] = {
                'label': '囤货倾向 📦',
                'detected': len(bulk) >= 5,
                'detail': f"疑似囤货消费 {len(bulk)} 次，金额 ¥{bulk['金额'].sum():.2f}",
                'severity': '高' if len(bulk) >= 15 else ('中' if len(bulk) >= 8 else '低')
            }
        else:
            patterns['囤货倾向'] = {'label': '囤货倾向 📦', 'detected': False, 'detail': '暂无囤货特征', 'severity': '无'}
    except Exception:
        patterns['囤货倾向'] = {'label': '囤货倾向 📦', 'detected': False, 'detail': '分析异常', 'severity': '无'}

    try:
        impulsive = df[df['情绪标签'].isin(['冲动', '后悔'])]
        if len(impulsive) > 0:
            pct = len(impulsive) / len(df) * 100
            patterns['冲动消费'] = {
                'label': '冲动消费 ⚡',
                'detected': pct >= 15,
                'detail': f"情绪驱动消费 {len(impulsive)} 次（占 {pct:.1f}%），金额 ¥{impulsive['金额'].sum():.2f}",
                'severity': '高' if pct >= 30 else ('中' if pct >= 20 else '低')
            }
        else:
            patterns['冲动消费'] = {'label': '冲动消费 ⚡', 'detected': False, 'detail': '暂无冲动消费记录', 'severity': '无'}
    except Exception:
        patterns['冲动消费'] = {'label': '冲动消费 ⚡', 'detected': False, 'detail': '分析异常', 'severity': '无'}

    try:
        if len(df) >= 30:
            cat_monthly = df.groupby(['月份', '类别'])['金额'].sum().unstack(fill_value=0)
            cat_std = cat_monthly.std()
            cat_mean = cat_monthly.mean()
            safe_mean = cat_mean.replace(0, np.nan)
            cv = (cat_std / safe_mean).fillna(0)
            unstable = cv[cv > 0.8]
            if len(unstable) > 0:
                worst_cat = str(cv.idxmax())
                patterns['消费波动'] = {
                    'label': '消费波动 📊',
                    'detected': True,
                    'detail': f"{worst_cat}类支出波动最大（变异系数 {cv[worst_cat]:.2f}），建议设置预算上限",
                    'severity': '高' if cv[worst_cat] > 1.5 else ('中' if cv[worst_cat] > 1.0 else '低')
                }
            else:
                patterns['消费波动'] = {'label': '消费波动 📊', 'detected': False, 'detail': '各类消费较稳定', 'severity': '无'}
        else:
            patterns['消费波动'] = {'label': '消费波动 📊', 'detected': False, 'detail': '数据不足，暂无法分析', 'severity': '无'}
    except Exception:
        patterns['消费波动'] = {'label': '消费波动 📊', 'detected': False, 'detail': '分析异常', 'severity': '无'}

    return patterns


def generate_budget_suggestion(df):
    if df.empty:
        return None
    try:
        monthly = df.groupby('月份')['金额'].sum()
        if len(monthly) == 0:
            return None
        avg_monthly = float(monthly.mean())
        cat_sum = df.groupby('类别')['金额'].sum()
        cat_avg = cat_sum / max(len(monthly), 1)

        suggestions = []
        total_budget = round(avg_monthly * 1.05, -1)
        savings_goal = round(total_budget * 0.15, -1)

        patterns = detect_patterns(df)

        budget_allocation = {}
        for cat in CATEGORIES:
            if cat in cat_avg.index:
                base = float(cat_avg[cat])
                adj = 1.0
                if patterns.get('冲动消费', {}).get('detected') and cat in ['购物', '娱乐']:
                    adj = 0.85
                    suggestions.append(f"【{cat}】受冲动消费影响，建议下调 15% 预算")
                if patterns.get('深夜购物', {}).get('detected') and cat in ['购物', '餐饮', '娱乐']:
                    adj *= 0.9
                    suggestions.append(f"【{cat}】深夜消费较多，设置月度上限 ¥{round(base * adj, -1):.0f}")
                if patterns.get('奶茶依赖', {}).get('detected') and cat == '餐饮':
                    adj *= 0.9
                    suggestions.append("【餐饮】奶茶依赖明显，建议设置饮品专项预算")
                if patterns.get('囤货倾向', {}).get('detected') and cat in ['居家', '购物']:
                    adj *= 0.92
                budget_allocation[cat] = round(base * adj, -1)
            else:
                budget_allocation[cat] = 0

        allocated = sum(budget_allocation.values())
        remaining = total_budget - savings_goal
        if allocated > remaining and allocated > 0:
            factor = remaining / allocated
            for k in budget_allocation:
                budget_allocation[k] = round(budget_allocation[k] * factor, -1)

        if not suggestions:
            suggestions.append("消费习惯整体良好，继续保持！")

        suggestions.append(f"建议下月总预算：¥{total_budget:.0f}，其中储蓄目标 ¥{savings_goal:.0f}")

        if len(monthly) >= 2:
            last_val = float(monthly.iloc[-1])
            trend = "上升" if last_val > avg_monthly else "下降"
            if trend == "上升":
                suggestions.append(f"⚠️ 近期支出呈{trend}趋势，上月 ¥{last_val:.2f} 高于月均 ¥{avg_monthly:.2f}")
            else:
                suggestions.append(f"✅ 近期支出呈{trend}趋势，继续保持")

        return {
            'total_budget': total_budget,
            'savings_goal': savings_goal,
            'allocation': budget_allocation,
            'suggestions': suggestions,
            'avg_monthly': avg_monthly,
            'last_month': float(monthly.iloc[-1]) if len(monthly) > 0 else 0
        }
    except Exception:
        traceback.print_exc()
        return None


def filter_dataframe(df, months, categories, payments, scenes, goals):
    filtered = df.copy()
    if months and len(months) > 0:
        filtered = filtered[filtered['月份'].isin(months)]
    if categories and len(categories) > 0:
        filtered = filtered[filtered['类别'].isin(categories)]
    if payments and len(payments) > 0:
        filtered = filtered[filtered['支付方式'].isin(payments)]
    if scenes and len(scenes) > 0:
        filtered = filtered[filtered['场景'].isin(scenes)]
    if goals and len(goals) > 0:
        filtered = filtered[filtered['消费目标'].isin(goals)]
    return filtered


def empty_fig(title="暂无数据"):
    fig = go.Figure()
    fig.update_layout(title=title, height=300, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def make_category_pie(df):
    if df.empty:
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


def make_budget_progress(df, budget_info):
    if df.empty:
        return empty_fig()
    try:
        monthly_sum = df.groupby('月份')['金额'].sum()
        if len(monthly_sum) == 0:
            return empty_fig()

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
    if df.empty:
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
    if df.empty:
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
    if df.empty:
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
    if df.empty:
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


SIDEBAR_STYLE = {
    "padding": "2rem 1rem",
    "backgroundColor": "#f8f9fa",
    "minHeight": "100vh",
}

app.layout = dbc.Container([
    html.H2([html.Span("📒 ", style={'marginRight': '10px'}), "手账消费记录与月度预算分析台"],
            className="text-center my-4",
            style={'color': '#343a40', 'fontWeight': 'bold'}),

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
                                html.P("支持列：日期/时间、金额/价格、类别/分类、支付方式、情绪标签、场景、消费目标、备注",
                                       className="text-center text-muted small mt-2 mb-0")
                            ])
                        ], className="border-primary border-dashed"),
                        multiple=False,
                        style={'width': '100%', 'cursor': 'pointer'}
                    ),
                    html.Div(id='file-status', className="mt-2 small text-info fw-bold")
                ], width=8),
                dbc.Col([
                    dbc.Button("使用示例数据", id='use-sample', color="secondary", className="w-100 mt-3", size="lg"),
                    html.P("点击按钮加载示例消费记录进行体验", className="text-center text-muted small mt-2")
                ], width=4)
            ])
        ])
    ], className="mb-4"),

    dbc.Card([
        dbc.CardHeader("🔍 筛选条件", className="bg-info text-white"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("月份"),
                    dcc.Dropdown(id='filter-months', multi=True, placeholder="选择月份...")
                ], width=3),
                dbc.Col([
                    html.Label("消费类别"),
                    dcc.Dropdown(id='filter-categories', multi=True, placeholder="选择类别...")
                ], width=3),
                dbc.Col([
                    html.Label("支付方式"),
                    dcc.Dropdown(id='filter-payments', multi=True, placeholder="选择支付方式...")
                ], width=3),
                dbc.Col([
                    html.Label("场景"),
                    dcc.Dropdown(id='filter-scenes', multi=True, placeholder="场景...")
                ], width=1.5),
                dbc.Col([
                    html.Label("消费目标"),
                    dcc.Dropdown(id='filter-goals', multi=True, placeholder="目标...")
                ], width=1.5),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Button("重置筛选", id='reset-filter', className="btn btn-outline-secondary mt-3 btn-sm")
                ])
            ])
        ])
    ], className="mb-4"),

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
                    html.H5("最大单笔", className="card-title text-muted"),
                    html.H3(id='kpi-max', className="text-danger", style={'fontWeight': 'bold'}),
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

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🔍 消费模式识别", className="bg-warning"),
                dbc.CardBody(id='patterns-card')
            ])
        ], width=5),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("💰 下月预算建议", className="bg-success text-white"),
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
)
def on_data_change(contents, n_clicks, filename):
    ctx = dash.callback_context
    trigger = ""
    if ctx.triggered:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger == 'upload-data' and contents:
        parse_contents(contents, filename or '')
    elif trigger == 'use-sample':
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
    Output('kpi-total', 'children'),
    Output('kpi-count', 'children'),
    Output('kpi-avg', 'children'),
    Output('kpi-max', 'children'),
    Output('chart-category-pie', 'figure'),
    Output('chart-budget-progress', 'figure'),
    Output('chart-heatmap', 'figure'),
    Output('chart-emotion-scatter', 'figure'),
    Output('chart-trend', 'figure'),
    Output('chart-payment', 'figure'),
    Output('patterns-card', 'children'),
    Output('budget-card', 'children'),
    Output('data-table', 'data'),
    Output('data-table', 'columns'),
    Input('filter-months', 'value'),
    Input('filter-categories', 'value'),
    Input('filter-payments', 'value'),
    Input('filter-scenes', 'value'),
    Input('filter-goals', 'value')
)
def update_dashboard(months, categories, payments, scenes, goals):
    try:
        if current_df is None or current_df.empty:
            fig = empty_fig()
            return "-", "-", "-", "-", fig, fig, fig, fig, fig, fig, html.Div("暂无数据"), html.Div("暂无数据"), [], []

        df = filter_dataframe(current_df, months, categories, payments, scenes, goals)

        if df.empty:
            fig = empty_fig("筛选后无数据")
            return "¥0", "0", "¥0", "¥0", fig, fig, fig, fig, fig, fig, html.Div("筛选后无数据"), html.Div("筛选后无数据"), [], []

        total = float(df['金额'].sum())
        count = len(df)
        avg = float(df['金额'].mean())
        max_v = float(df['金额'].max())

        budget_info = generate_budget_suggestion(current_df)
        patterns = detect_patterns(current_df)

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
                    html.Div([html.Strong(info.get('label', key)), dbc.Badge(badge_text, color=badge_color, className="ms-2")]),
                    html.Small(info.get('detail', ''), className="text-muted d-block mt-1")
                ], className="mb-2")
            )
        patterns_content = dbc.ListGroup(pattern_items, className="list-group-flush")

        if budget_info:
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
            budget_content = dbc.Row([
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
        else:
            budget_content = html.Div("暂无足够数据生成建议")

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
            f"¥{max_v:,.2f}",
            make_category_pie(df),
            make_budget_progress(df, budget_info),
            make_heatmap(df),
            make_emotion_scatter(df),
            make_trend_chart(df),
            make_payment_chart(df),
            patterns_content,
            budget_content,
            table_data,
            columns
        )
    except Exception:
        traceback.print_exc()
        err_fig = empty_fig("内部错误")
        err_msg = html.Div([html.H5("发生错误", className="text-danger"), html.Pre(traceback.format_exc(), className="small")])
        return "-", "-", "-", "-", err_fig, err_fig, err_fig, err_fig, err_fig, err_fig, err_msg, err_msg, [], []


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=9201)
