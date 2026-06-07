import traceback
from datetime import datetime

import numpy as np
import pandas as pd

from data_parser import CATEGORIES


def detect_patterns(df):
    patterns = {}
    if df.empty:
        return patterns

    try:
        note_mask = df['备注'].astype(str).str.contains(
            r'奶茶|咖啡|星巴克|瑞幸|喜茶|奈雪|蜜雪|一点点|coco|茶百道|古茗|霸王茶姬|沪上阿姨|茶颜|冰美式|拿铁|卡布奇诺|摩卡|星冰乐|脏脏茶|芋泥啵啵|杨枝甘露|水果茶',
            case=False, na=False
        )
        drinks_keyword = df[note_mask]

        price_range = (df['金额'] >= 10) & (df['金额'] <= 35)
        tea_time = (df['小时'] >= 9) & (df['小时'] <= 11) | (df['小时'] >= 13) & (df['小时'] <= 17)
        category_match = df['类别'] == '餐饮'
        probable_drinks = df[price_range & tea_time & category_match & ~note_mask]

        milk_tea = pd.concat([drinks_keyword, probable_drinks]).drop_duplicates()

        if len(milk_tea) > 0:
            monthly = milk_tea.groupby('月份').size()
            avg_monthly = float(monthly.mean()) if len(monthly) > 0 else 0
            keyword_cnt = len(drinks_keyword)
            inferred_cnt = len(probable_drinks)
            patterns['奶茶依赖'] = {
                'label': '奶茶/咖啡依赖 🧋',
                'detected': avg_monthly >= 6,
                'detail': (f"月均 {avg_monthly:.1f} 杯，累计消费 ¥{milk_tea['金额'].sum():.2f}"
                           f"（关键词识别{keyword_cnt}次，时段推断{inferred_cnt}次）"),
                'severity': '高' if avg_monthly >= 12 else ('中' if avg_monthly >= 8 else '低')
            }
        else:
            patterns['奶茶依赖'] = {'label': '奶茶/咖啡依赖 🧋', 'detected': False, 'detail': '暂无饮品高频消费', 'severity': '无'}
    except Exception:
        patterns['奶茶依赖'] = {'label': '奶茶/咖啡依赖 🧋', 'detected': False, 'detail': '分析异常', 'severity': '无'}

    try:
        late_hours = (df['小时'] >= 22) | (df['小时'] <= 2)
        shopping_cats = df['类别'].isin(['购物', '娱乐'])
        emotional = df['情绪标签'].isin(['冲动', '后悔', '开心'])
        late_night = df[late_hours & (shopping_cats | emotional)]
        if len(late_night) > 0:
            pct = len(late_night) / len(df) * 100
            shop_count = len(late_night[late_night['类别'] == '购物'])
            ent_count = len(late_night[late_night['类别'] == '娱乐'])
            food_count = len(late_night[late_night['类别'] == '餐饮'])
            detail = (f"深夜非刚需消费 {len(late_night)} 次，占比 {pct:.1f}%，金额 ¥{late_night['金额'].sum():.2f}"
                      f"（购物{shop_count}次/娱乐{ent_count}次/夜宵{food_count}次）")
            patterns['深夜购物'] = {
                'label': '深夜非刚需消费 🌙',
                'detected': pct >= 10,
                'detail': detail,
                'severity': '高' if pct >= 25 else ('中' if pct >= 15 else '低')
            }
        else:
            patterns['深夜购物'] = {'label': '深夜非刚需消费 🌙', 'detected': False, 'detail': '无深夜冲动消费记录', 'severity': '无'}
    except Exception:
        patterns['深夜购物'] = {'label': '深夜非刚需消费 🌙', 'detected': False, 'detail': '分析异常', 'severity': '无'}

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


def default_budget_config(df):
    config = {}
    if df is None or df.empty:
        for cat in CATEGORIES:
            config[cat] = {
                'budget': 0,
                'flex_range': 10,
                'necessary_weight': 50,
                'holiday_factor': 1.2
            }
        return config

    try:
        monthly = df.groupby('月份')['金额'].sum()
        n_months = max(len(monthly), 1)
        cat_monthly = df.groupby(['月份', '类别'])['金额'].sum().unstack(fill_value=0)

        necessary_map = {
            '餐饮': 80, '交通': 85, '居家': 90, '医疗': 95, '教育': 75,
            '购物': 30, '娱乐': 20, '旅行': 25, '其他': 50
        }
        holiday_map = {
            '餐饮': 1.3, '购物': 1.5, '娱乐': 1.4, '旅行': 2.0, '交通': 1.2,
            '居家': 1.1, '医疗': 1.0, '教育': 1.0, '其他': 1.1
        }

        for cat in CATEGORIES:
            if cat in cat_monthly.columns:
                avg = float(cat_monthly[cat].mean())
                base = round(avg * 1.05, -1)
            else:
                base = 0
            config[cat] = {
                'budget': base,
                'flex_range': 10,
                'necessary_weight': necessary_map.get(cat, 50),
                'holiday_factor': holiday_map.get(cat, 1.2)
            }
    except Exception:
        traceback.print_exc()
        for cat in CATEGORIES:
            config[cat] = {
                'budget': 0,
                'flex_range': 10,
                'necessary_weight': 50,
                'holiday_factor': 1.2
            }
    return config


def is_holiday_month(month_str):
    try:
        parts = month_str.split('-')
        if len(parts) < 2:
            return False
        m = int(parts[1])
        return m in [1, 2, 5, 10, 12]
    except Exception:
        return False


def compute_adjusted_budget(budget_config, month_str, savings_goal=0):
    adjusted = {}
    total_adj = 0
    holiday = is_holiday_month(month_str)
    for cat in CATEGORIES:
        cfg = budget_config.get(cat, {})
        base = float(cfg.get('budget', 0))
        h_factor = float(cfg.get('holiday_factor', 1.0)) if holiday else 1.0
        adj_val = round(base * h_factor, -1)
        adjusted[cat] = adj_val
        total_adj += adj_val

    if total_adj > 0 and savings_goal > 0:
        factor = max(0, (total_adj - savings_goal) / total_adj)
        for cat in adjusted:
            adjusted[cat] = round(adjusted[cat] * factor, -1)

    return adjusted, holiday


def detect_abnormal_expenses(df, budget_config, month_str=None):
    if df is None or df.empty:
        return pd.DataFrame()

    work_df = df.copy()
    if month_str:
        work_df = work_df[work_df['月份'] == month_str]
    if work_df.empty:
        return pd.DataFrame()

    cat_monthly = work_df.groupby('类别')['金额'].sum()
    results = []

    for cat in CATEGORIES:
        spent = float(cat_monthly.get(cat, 0))
        cfg = budget_config.get(cat, {})
        budget = float(cfg.get('budget', 0))
        flex = float(cfg.get('flex_range', 10)) / 100.0
        flex_budget = budget * (1 + flex)

        if budget <= 0 or spent <= 0:
            continue

        cat_rows = work_df[work_df['类别'] == cat]

        over_amount = max(0, spent - budget)
        if over_amount <= 0:
            continue

        reasons = {}
        remaining = over_amount

        onetime_threshold = budget * 0.3
        onetime_rows = cat_rows[cat_rows['金额'] >= onetime_threshold]
        onetime_total = float(onetime_rows['金额'].sum()) if len(onetime_rows) > 0 else 0
        if onetime_total > 0:
            onetime_contrib = min(remaining, onetime_total * 0.6)
            if onetime_contrib > 10:
                reasons['一次性大额支出'] = round(onetime_contrib, 2)
                remaining -= onetime_contrib

        if is_holiday_month(str(cat_rows['月份'].iloc[0]) if len(cat_rows) > 0 else ''):
            h_factor = float(cfg.get('holiday_factor', 1.0))
            holiday_extra = budget * max(0, (h_factor - 1))
            if holiday_extra > 0 and remaining > 0:
                contrib = min(remaining, holiday_extra)
                if contrib > 10:
                    reasons['节假日波动'] = round(contrib, 2)
                    remaining -= contrib

        emotional_rows = cat_rows[cat_rows['情绪标签'].isin(['冲动', '后悔', '焦虑'])]
        emotional_total = float(emotional_rows['金额'].sum()) if len(emotional_rows) > 0 else 0
        if emotional_total > 0 and remaining > 0:
            contrib = min(remaining, emotional_total * 0.7)
            if contrib > 10:
                reasons['情绪驱动超支'] = round(contrib, 2)
                remaining -= contrib

        if remaining > 10:
            reasons['结构性超支'] = round(remaining, 2)

        if reasons:
            results.append({
                '类别': cat,
                '预算': round(budget, 2),
                '实际支出': round(spent, 2),
                '超支金额': round(over_amount, 2),
                '超支比例': round(over_amount / budget * 100, 1),
                '归因': reasons
            })

    return pd.DataFrame(results)


def build_budget_timeseries(df, budget_config, savings_goal=0):
    if df is None or df.empty:
        return pd.DataFrame()

    months = sorted(df['月份'].unique())
    rows = []
    for m in months:
        m_df = df[df['月份'] == m]
        actual = float(m_df['金额'].sum())
        adjusted, is_holiday = compute_adjusted_budget(budget_config, m, savings_goal)
        plan_total = sum(float(budget_config.get(c, {}).get('budget', 0)) for c in CATEGORIES)
        adj_total = sum(adjusted.values())
        rows.append({
            '月份': m,
            '实际支出': round(actual, 2),
            '计划预算': round(plan_total, 2),
            '调整后预算': round(adj_total, 2),
            '节假日': is_holiday
        })

    return pd.DataFrame(rows)


def simulate_next_month_budget(budget_config, savings_goal, df=None, patterns=None):
    result = {
        'original_total': 0,
        'adjusted_total': 0,
        'savings_goal': savings_goal,
        'projected_spending': 0,
        'category_detail': [],
        'warnings': [],
        'tips': []
    }

    for cat in CATEGORIES:
        cfg = budget_config.get(cat, {})
        budget = float(cfg.get('budget', 0))
        flex = float(cfg.get('flex_range', 10))
        nec_weight = float(cfg.get('necessary_weight', 50))
        holiday_factor = float(cfg.get('holiday_factor', 1.2))

        projected = budget * holiday_factor
        result['original_total'] += budget
        result['projected_spending'] += projected
        result['category_detail'].append({
            '类别': cat,
            '原预算': round(budget, 2),
            '弹性上限(%)': flex,
            '必要权重(%)': nec_weight,
            '节假日系数': holiday_factor,
            '预测支出': round(projected, 2)
        })

    result['adjusted_total'] = round(max(0, result['projected_spending'] - savings_goal), 2)
    result['original_total'] = round(result['original_total'], 2)
    result['projected_spending'] = round(result['projected_spending'], 2)

    if patterns:
        for key, info in patterns.items():
            if info.get('detected'):
                result['warnings'].append(f"{info.get('label', key)}: {info.get('detail', '')}")

    if df is not None and not df.empty:
        last_months = sorted(df['月份'].unique())[-3:]
        recent_avg = df[df['月份'].isin(last_months)]['金额'].sum() / max(len(last_months), 1)
        if recent_avg > result['adjusted_total'] * 1.1:
            result['warnings'].append(
                f"近{len(last_months)}个月平均支出 ¥{recent_avg:.0f} 高于调整后预算，需关注超支风险"
            )
        else:
            result['tips'].append("当前预算配置与历史支出水平基本匹配")

    if result['adjusted_total'] > 0:
        saving_rate = savings_goal / (result['adjusted_total'] + savings_goal) * 100
        if saving_rate >= 20:
            result['tips'].append(f"储蓄率 {saving_rate:.0f}%，表现优秀！")
        elif saving_rate >= 10:
            result['tips'].append(f"储蓄率 {saving_rate:.0f}%，建议进一步提升至 20%")
        else:
            result['warnings'].append(f"储蓄率仅 {saving_rate:.0f}%，建议压缩非必要支出")

    return result
