"""回归曲线分析：五年之锚 / 对数回归"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


class RegressionAnalyzer:
    """回归曲线分析器

    实现"五年之锚"等对数回归分析：
    ln(Price) = a * ln(t) + b
    叠加置信区间判断当前估值位置
    """

    def fit_log_regression(
        self,
        price_series: pd.Series,
        sigma_bands: float = 1.5,
    ) -> dict:
        """对数回归拟合

        Args:
            price_series: 价格时间序列（需已去除 NaN）
            sigma_bands: 置信区间的 sigma 倍数

        Returns:
            dict: {
                fitted_values, upper_band, lower_band,
                current_position, slope, r_squared
            }
        """
        prices = price_series.dropna().values
        if len(prices) < 30:
            return {}

        t = np.arange(1, len(prices) + 1, dtype=float)
        ln_price = np.log(prices)
        ln_t = np.log(t)

        slope, intercept, r_value, p_value, std_err = stats.linregress(ln_t, ln_price)
        r_squared = r_value ** 2

        fitted_ln = slope * ln_t + intercept
        residuals = ln_price - fitted_ln
        residual_std = residuals.std()

        fitted_values = np.exp(fitted_ln)
        upper_band = np.exp(fitted_ln + sigma_bands * residual_std)
        lower_band = np.exp(fitted_ln - sigma_bands * residual_std)

        # 当前价格在通道中的位置 (-1 ~ 1, 0=中轨)
        current_residual = residuals[-1]
        position = current_residual / (sigma_bands * residual_std) if residual_std > 0 else 0

        return {
            "fitted_values": fitted_values,
            "upper_band": upper_band,
            "lower_band": lower_band,
            "current_position": round(float(position), 3),
            "slope": round(float(slope), 4),
            "r_squared": round(float(r_squared), 4),
            "current_price": float(prices[-1]),
            "fitted_price": float(fitted_values[-1]),
            "upper_price": float(upper_band[-1]),
            "lower_price": float(lower_band[-1]),
        }

    def get_anchor_signal(self, position: float) -> dict:
        """根据回归位置给出信号

        position: -1 (下轨) ~ 0 (中轨) ~ 1 (上轨)
        """
        if position < -0.8:
            return {"signal": "强烈看多", "zone": "极度低估", "description": "接近下轨，历史极值"}
        elif position < -0.3:
            return {"signal": "看多", "zone": "低估", "description": "低于中轨较多"}
        elif position < 0.3:
            return {"signal": "中性", "zone": "适中", "description": "中轨附近"}
        elif position < 0.8:
            return {"signal": "看空", "zone": "高估", "description": "高于中轨较多"}
        else:
            return {"signal": "强烈看空", "zone": "极度高估", "description": "接近上轨，警惕回归"}
