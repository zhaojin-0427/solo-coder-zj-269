import base64
import io
import traceback

import numpy as np
import pandas as pd

CATEGORIES = ['餐饮', '购物', '交通', '娱乐', '居家', '医疗', '教育', '旅行', '其他']
PAYMENT_METHODS = ['微信', '支付宝', '信用卡', '现金', '银行卡', '花呗', '其他']
EMOTIONS = ['开心', '平静', '焦虑', '冲动', '后悔', '满足', '疲惫']
SCENES = ['日常', '聚餐', '通勤', '约会', '购物日', '节日', '旅行', '加班']
GOALS = ['刚需', '改善生活', '社交', '兴趣爱好', '应急', '储蓄', '其他']


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


def parse_contents(contents, filename):
    if contents is None:
        return None, "未上传文件"
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        if 'csv' in filename.lower():
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename.lower():
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None, "不支持的文件格式，请使用 CSV 或 Excel"

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
            return None, "CSV 需包含 日期/时间 和 金额/价格 列"

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

        return df.reset_index(drop=True), f"成功加载 {len(df)} 条记录"
    except Exception as e:
        traceback.print_exc()
        return None, f"解析错误: {str(e)}"


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
