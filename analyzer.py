import traceback

import numpy as np
import pandas as pd

from data_parser import CATEGORIES


def default_budget_config():
    config = {}
    default_weights = {
        '餐饮': 1.0, '购物': 0.6, '交通': 1.0, '娱乐': 0.5,
        '居家': 1.0, '医疗': 1.0, '教育': 1.0, '旅行': 0.4, '其他': 0.7
    }
    for cat in CATEGORIES:
        config[cat] = {
            'monthly_budget': 0.0,
            'flex_range': 0.15,
            'necessity_weight': default_weights.get(cat, 0.7),
            'holiday_coeff': 1.3
        }
    return config


def init_budget_from_history(df):
    config = default_budget_config()
    if df is None or df.empty:
        return config
    try:
        monthly = df.groupby('月份')['金额'].sum()
        month_count = max(len(monthly), 1)
        cat_avg = df.groupby('类别')['金额'].sum() / month_count
        for cat in CATEGORIES:
            base = float(cat_avg.get(cat, 0))
            config[cat]['monthly_budget'] = round(base * 1.05, -1) if base > 0 else 100.0
        return config
    except Exception:
        traceback.print_exc()
        return config


def detect_patterns(df):
    patterns = {}
    if df is None or df.empty:
        return patterns

    try:
        note_mask = df['备注'].astype(str).str.contains(
            r'奶茶|咖啡|星巴克|瑞幸|喜茶|奈雪|蜜雪|一点点|coco|茶百道|古茗|霸王茶姬|沪上阿姨|茶颜|冰美式|拿铁|卡布奇诺|摩卡|星冰乐|脏脏茶|芋泥啵啵|杨枝甘露|水果茶',
            case=False, na=False
        )
        drinks_keyword = df[note_mask]

        price_range = (df['金额'] >= 10) & (df['金额'] <= 35)
        tea_time = ((df['小时'] >= 9) & (df['小时'] <= 11)) | ((df['小时'] >= 13) & (df['小时'] <= 17))
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


def compute_monthly_budget_series(df, budget_config, savings_goal=0):
    if df is None or df.empty:
        return pd.DataFrame()
    try:
        months = sorted(df['月份'].unique())
        actual = df.groupby('月份')['金额'].sum()

        records = []
        total_plan = sum(v['monthly_budget'] for v in budget_config.values())

        for m in months:
            plan = total_plan
            month_dt = pd.to_datetime(m + '-01')
            is_holiday_month = month_dt.month in [1, 2, 5, 10]

            adjusted = total_plan
            if is_holiday_month:
                holiday_boost = 0
                for cat, cfg in budget_config.items():
                    holiday_boost += cfg['monthly_budget'] * (cfg['holiday_coeff'] - 1)
                adjusted = total_plan + holiday_boost

            flex = total_plan * 0.1
            adjusted += flex

            records.append({
                '月份': m,
                '实际支出': float(actual.get(m, 0)),
                '计划预算': round(plan, 2),
                '调整后预算': round(adjusted, 2),
                '储蓄目标': round(savings_goal, 2),
                '是否节假日月': is_holiday_month
            })

        result = pd.DataFrame(records)
        result['预算执行率'] = (result['实际支出'] / result['计划预算'] * 100).round(1)
        result['超支金额'] = (result['实际支出'] - result['调整后预算']).round(2)
        return result
    except Exception:
        traceback.print_exc()
        return pd.DataFrame()


def detect_abnormal_expenses(df, budget_config):
    if df is None or df.empty:
        return pd.DataFrame()

    try:
        months = sorted(df['月份'].unique())
        if len(months) == 0:
            return pd.DataFrame()

        cat_monthly_avg = {}
        for cat in CATEGORIES:
            cat_data = df[df['类别'] == cat]
            if len(cat_data) > 0:
                monthly = cat_data.groupby('月份')['金额'].sum()
                cat_monthly_avg[cat] = {
                    'avg': float(monthly.mean()) if len(monthly) > 0 else 0,
                    'std': float(monthly.std()) if len(monthly) > 1 else 0,
                    'max_single': float(cat_data['金额'].max()) if len(cat_data) > 0 else 0
                }

        abnormals = []

        for _, row in df.iterrows():
            amount = float(row['金额'])
            cat = row['类别']
            emotion = row['情绪标签']
            scene = row['场景']
            month = row['月份']
            month_dt = pd.to_datetime(month + '-01')
            is_holiday = month_dt.month in [1, 2, 5, 10]

            reasons = []
            cat_budget = budget_config.get(cat, {}).get('monthly_budget', 100)
            necessity = budget_config.get(cat, {}).get('necessity_weight', 0.7)

            cat_stats = cat_monthly_avg.get(cat, {'avg': 0, 'std': 0, 'max_single': 0})

            is_structural = False
            if cat_stats['std'] > 0 and necessity >= 0.8:
                monthly_cat = df[(df['类别'] == cat) & (df['月份'] == month)]['金额'].sum()
                if monthly_cat > cat_budget * 1.1 and cat_stats['avg'] > 0:
                    is_structural = True
                    reasons.append('结构性超支')

            is_emotional = False
            if emotion in ['冲动', '后悔', '焦虑'] and amount > cat_budget * 0.2:
                is_emotional = True
                reasons.append('情绪驱动超支')

            is_holiday_effect = False
            if is_holiday and (scene in ['节日', '旅行', '聚餐'] or amount > cat_budget * 0.5):
                is_holiday_effect = True
                reasons.append('节假日波动')

            is_large_one_off = False
            if amount > cat_stats['max_single'] * 0.8 and amount > 500:
                is_large_one_off = True
                reasons.append('一次性大额支出')

            if reasons:
                abnormals.append({
                    '日期': row['日期'],
                    '金额': amount,
                    '类别': cat,
                    '支付方式': row['支付方式'],
                    '情绪标签': emotion,
                    '场景': scene,
                    '消费目标': row['消费目标'],
                    '备注': row['备注'],
                    '超支原因': '、'.join(reasons),
                    '结构性超支': is_structural,
                    '情绪驱动超支': is_emotional,
                    '节假日波动': is_holiday_effect,
                    '一次性大额支出': is_large_one_off,
                    '严重程度': len(reasons)
                })

        result = pd.DataFrame(abnormals)
        if not result.empty:
            result = result.sort_values(['严重程度', '金额'], ascending=[False, False]).reset_index(drop=True)
        return result
    except Exception:
        traceback.print_exc()
        return pd.DataFrame()


def analyze_overspend_causes(abnormal_df, budget_config):
    causes = {
        '结构性超支': {'count': 0, 'amount': 0.0, 'categories': {}},
        '情绪驱动超支': {'count': 0, 'amount': 0.0, 'categories': {}},
        '节假日波动': {'count': 0, 'amount': 0.0, 'categories': {}},
        '一次性大额支出': {'count': 0, 'amount': 0.0, 'categories': {}}
    }
    if abnormal_df is None or abnormal_df.empty:
        return causes

    try:
        cause_map = {
            '结构性超支': '结构性超支',
            '情绪驱动超支': '情绪驱动超支',
            '节假日波动': '节假日波动',
            '一次性大额支出': '一次性大额支出'
        }
        for _, row in abnormal_df.iterrows():
            for cause_key, cause_name in cause_map.items():
                if row.get(cause_key, False):
                    causes[cause_name]['count'] += 1
                    causes[cause_name]['amount'] += float(row['金额'])
                    cat = row['类别']
                    causes[cause_name]['categories'][cat] = causes[cause_name]['categories'].get(cat, 0) + float(row['金额'])
        for k in causes:
            causes[k]['amount'] = round(causes[k]['amount'], 2)
            for c in causes[k]['categories']:
                causes[k]['categories'][c] = round(causes[k]['categories'][c], 2)
        return causes
    except Exception:
        traceback.print_exc()
        return causes


def simulate_next_month_budget(df, budget_config, savings_goal, adjustment_factor=1.0,
                               holiday_next=False, patterns=None):
    try:
        result = {}
        total = 0.0
        suggestions = []

        for cat in CATEGORIES:
            cfg = budget_config.get(cat, default_budget_config()[cat])
            base = cfg['monthly_budget']

            adj = adjustment_factor

            if patterns:
                if patterns.get('冲动消费', {}).get('detected') and cat in ['购物', '娱乐']:
                    adj *= 0.85
                if patterns.get('深夜购物', {}).get('detected') and cat in ['购物', '餐饮', '娱乐']:
                    adj *= 0.92
                if patterns.get('奶茶依赖', {}).get('detected') and cat == '餐饮':
                    adj *= 0.93
                if patterns.get('囤货倾向', {}).get('detected') and cat in ['居家', '购物']:
                    adj *= 0.95

            necessity = cfg['necessity_weight']
            if necessity < 0.6:
                adj *= 0.95
                suggestions.append(f"【{cat}】非必要支出，适度下调预算")

            final_budget = round(base * adj, -1)
            if holiday_next:
                final_budget = round(final_budget * cfg['holiday_coeff'], -1)
                suggestions.append(f"【{cat}】下月为节假日月，已应用节假日系数 {cfg['holiday_coeff']}")

            flex_amount = round(final_budget * cfg['flex_range'], -1)
            result[cat] = {
                'base_budget': final_budget,
                'flex_lower': round(final_budget - flex_amount, -1),
                'flex_upper': round(final_budget + flex_amount, -1),
                'flex_range_pct': cfg['flex_range'] * 100,
                'necessity_weight': necessity,
                'holiday_coeff': cfg['holiday_coeff']
            }
            total += final_budget

        result['_totals'] = {
            'total_budget': round(total, -1),
            'savings_goal': round(savings_goal, -1),
            'total_with_savings': round(total + savings_goal, -1)
        }

        if df is not None and not df.empty:
            monthly = df.groupby('月份')['金额'].sum()
            if len(monthly) > 0:
                avg_m = float(monthly.mean())
                last_m = float(monthly.iloc[-1])
                if last_m > avg_m * 1.1:
                    suggestions.append(f"⚠️ 上月支出 ¥{last_m:.0f} 高于月均 ¥{avg_m:.0f}，建议提高关注度")
                elif last_m < avg_m * 0.9:
                    suggestions.append(f"✅ 上月支出 ¥{last_m:.0f} 低于月均 ¥{avg_m:.0f}，表现良好")

        if not suggestions:
            suggestions.append("消费习惯整体良好，继续保持！")

        result['_suggestions'] = suggestions
        return result
    except Exception:
        traceback.print_exc()
        return {}


def generate_budget_suggestion(df):
    if df is None or df.empty:
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


def compute_budget_execution(df, budget_config, target_month=None):
    if df is None or df.empty:
        return {}
    try:
        if target_month is None:
            months = sorted(df['月份'].unique())
            if not months:
                return {}
            target_month = months[-1]

        month_data = df[df['月份'] == target_month]
        result = {}
        for cat in CATEGORIES:
            cat_data = month_data[month_data['类别'] == cat]
            spent = float(cat_data['金额'].sum())
            cfg = budget_config.get(cat, {})
            budget = float(cfg.get('monthly_budget', 0))
            flex = float(cfg.get('flex_range', 0.15))
            flex_upper = budget * (1 + flex)
            pct = (spent / budget * 100) if budget > 0 else 0
            status = '超支' if spent > flex_upper else ('预警' if spent > budget else '健康')
            color = '#d62728' if status == '超支' else ('#ff7f0e' if status == '预警' else '#2ca02c')
            result[cat] = {
                'spent': round(spent, 2),
                'budget': round(budget, 2),
                'flex_upper': round(flex_upper, 2),
                'execution_pct': round(pct, 1),
                'status': status,
                'color': color,
                'overrun': round(max(spent - budget, 0), 2)
            }
        return result
    except Exception:
        traceback.print_exc()
        return {}
