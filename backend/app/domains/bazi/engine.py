"""八字排盘引擎 — 命理规则计算（从旧项目迁移）"""

from typing import Dict, List, Optional


class BaziRuleEngine:
    """八字规则引擎"""

    def __init__(self):
        self.tiangan = "甲乙丙丁戊己庚辛壬癸"
        self.dizhi = "子丑寅卯辰巳午未申酉戌亥"
        self.wuxing_map = {
            "甲": "木", "乙": "木", "丙": "火", "丁": "火",
            "戊": "土", "己": "土", "庚": "金", "辛": "金",
            "壬": "水", "癸": "水",
            "子": "水", "丑": "土", "寅": "木", "卯": "木",
            "辰": "土", "巳": "火", "午": "火", "未": "土",
            "申": "金", "酉": "金", "戌": "土", "亥": "水",
        }
        self.shichen_dizhi = {
            "子时": "子", "丑时": "丑", "寅时": "寅", "卯时": "卯",
            "辰时": "辰", "巳时": "巳", "午时": "午", "未时": "未",
            "申时": "申", "酉时": "酉", "戌时": "戌", "亥时": "亥",
        }

    def calculate(self, birth_year: str, birth_month: str, birth_day: str,
                  birth_hour: str, gender: str) -> Dict:
        """
        根据出生信息计算八字

        Returns:
            包含八字、五行、格局分析等的字典
        """
        try:
            year = int(birth_year)
            month = int(birth_month)
            day = int(birth_day)
        except (ValueError, TypeError):
            return {"error": "出生日期格式不正确"}

        # 计算年柱
        year_gan, year_zhi = self._year_pillar(year)
        # 计算月柱
        month_gan, month_zhi = self._month_pillar(year, month)
        # 计算日柱
        day_gan, day_zhi = self._day_pillar(year, month, day)
        # 计算时柱
        hour_dizhi = self.shichen_dizhi.get(birth_hour, "子")
        hour_gan, hour_zhi = self._hour_pillar(day_gan, hour_dizhi)

        # 日主
        ri_zhu = day_gan
        ri_zhu_wuxing = self.wuxing_map.get(ri_zhu, "")

        # 五行统计
        all_chars = [year_gan, year_zhi, month_gan, month_zhi,
                     day_gan, day_zhi, hour_gan, hour_zhi]
        wuxing_count = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
        for c in all_chars:
            wx = self.wuxing_map.get(c, "")
            if wx:
                wuxing_count[wx] += 1

        # 身旺身弱判断
        same_element = wuxing_count.get(ri_zhu_wuxing, 0)
        sheng_element = self._sheng_wo(ri_zhu_wuxing)
        same_count = same_element + wuxing_count.get(sheng_element, 0)
        is_strong = same_count >= 4

        # 用神忌神
        yong_shen, ji_shen = self._calc_yongshen(ri_zhu_wuxing, is_strong)

        # 大运（简化计算）
        dayun = self._calc_dayun(year_gan, month_gan, month_zhi, gender, year)

        # 格局分析
        structure = self._analyze_structure(
            ri_zhu_wuxing, is_strong, wuxing_count, month_zhi
        )

        bazi_str = f"{year_gan}{year_zhi} {month_gan}{month_zhi} {day_gan}{day_zhi} {hour_gan}{hour_zhi}"

        return {
            "八字": bazi_str,
            "年柱": f"{year_gan}{year_zhi}",
            "月柱": f"{month_gan}{month_zhi}",
            "日柱": f"{day_gan}{day_zhi}",
            "时柱": f"{hour_gan}{hour_zhi}",
            "日主": f"{ri_zhu}({ri_zhu_wuxing})",
            "五行分布": wuxing_count,
            "身强身弱": "身旺" if is_strong else "身弱",
            "用神": yong_shen,
            "忌神": ji_shen,
            "格局": structure,
            "大运": dayun,
            "性别": gender,
        }

    def _year_pillar(self, year: int):
        """年柱"""
        gan_idx = (year - 4) % 10
        zhi_idx = (year - 4) % 12
        return self.tiangan[gan_idx], self.dizhi[zhi_idx]

    def _month_pillar(self, year: int, month: int):
        """月柱（简化：不考虑节气精确边界）"""
        year_gan_idx = (year - 4) % 10
        month_gan_base = (year_gan_idx % 5) * 2
        month_gan_idx = (month_gan_base + month - 1) % 10
        month_zhi_idx = (month + 1) % 12
        return self.tiangan[month_gan_idx], self.dizhi[month_zhi_idx]

    def _day_pillar(self, year: int, month: int, day: int):
        """日柱（简化公式）"""
        # 使用基姆拉尔森公式的变体估算
        if month <= 2:
            month += 12
            year -= 1
        c = year // 100
        y = year % 100
        total = int(y + y // 4 + c // 4 - 2 * c + 26 * (month + 1) // 10 + day - 1)
        gan_idx = (total % 10 + 10) % 10
        zhi_idx = (total % 12 + 12) % 12
        return self.tiangan[gan_idx], self.dizhi[zhi_idx]

    def _hour_pillar(self, day_gan: str, hour_dizhi: str):
        """时柱"""
        day_gan_idx = self.tiangan.index(day_gan)
        hour_zhi_idx = self.dizhi.index(hour_dizhi)
        hour_gan_base = (day_gan_idx % 5) * 2
        hour_gan_idx = (hour_gan_base + hour_zhi_idx) % 10
        return self.tiangan[hour_gan_idx], hour_dizhi

    def _sheng_wo(self, wuxing: str) -> str:
        """生我者"""
        sheng_map = {"金": "土", "木": "水", "水": "金", "火": "木", "土": "火"}
        return sheng_map.get(wuxing, "")

    def _calc_yongshen(self, ri_zhu_wx: str, is_strong: bool):
        """计算用神忌神"""
        ke_map = {"金": "木", "木": "土", "水": "火", "火": "金", "土": "水"}
        xie_map = {"金": "水", "木": "火", "水": "木", "火": "土", "土": "金"}
        sheng_map = {"金": "土", "木": "水", "水": "金", "火": "木", "土": "火"}

        if is_strong:
            yong = [ke_map.get(ri_zhu_wx, ""), xie_map.get(ri_zhu_wx, "")]
            ji = [ri_zhu_wx, sheng_map.get(ri_zhu_wx, "")]
        else:
            yong = [ri_zhu_wx, sheng_map.get(ri_zhu_wx, "")]
            ji = [ke_map.get(ri_zhu_wx, ""), xie_map.get(ri_zhu_wx, "")]

        return [x for x in yong if x], [x for x in ji if x]

    def _calc_dayun(self, year_gan, month_gan, month_zhi, gender, year):
        """简化大运计算"""
        year_gan_idx = self.tiangan.index(year_gan)
        is_yang = year_gan_idx % 2 == 0
        is_male = gender == "男"
        forward = (is_yang and is_male) or (not is_yang and not is_male)

        month_gan_idx = self.tiangan.index(month_gan)
        month_zhi_idx = self.dizhi.index(month_zhi)

        dayun = []
        for i in range(1, 9):
            if forward:
                g = self.tiangan[(month_gan_idx + i) % 10]
                z = self.dizhi[(month_zhi_idx + i) % 12]
            else:
                g = self.tiangan[(month_gan_idx - i) % 10]
                z = self.dizhi[(month_zhi_idx - i) % 12]
            start_age = i * 10
            dayun.append({
                "干支": f"{g}{z}",
                "年龄段": f"{start_age - 9}-{start_age}岁",
                "五行": f"{self.wuxing_map.get(g, '')}{self.wuxing_map.get(z, '')}",
            })
        return dayun

    def _analyze_structure(self, ri_zhu_wx, is_strong, wuxing_count, month_zhi):
        """格局分析"""
        month_wx = self.wuxing_map.get(month_zhi, "")
        ke_map = {"金": "木", "木": "土", "水": "火", "火": "金", "土": "水"}
        sheng_map = {"金": "土", "木": "水", "水": "金", "火": "木", "土": "火"}
        xie_map = {"金": "水", "木": "火", "水": "木", "火": "土", "土": "金"}

        # 判断格局
        if is_strong and wuxing_count.get(xie_map.get(ri_zhu_wx, ""), 0) >= 2:
            return "伤官生财格 — 聪明能干，适合技术、创意、商业"
        if not is_strong and wuxing_count.get(sheng_map.get(ri_zhu_wx, ""), 0) >= 2:
            return "官印相生格 — 贵气，适合管理、公职、权威"
        if is_strong and wuxing_count.get(ke_map.get(ri_zhu_wx, ""), 0) >= 2:
            return "财官格 — 富贵，适合商业、投资"
        if is_strong:
            return "身旺格 — 精力旺盛，需泄耗，宜外向发展"
        else:
            return "身弱格 — 需扶助，宜稳健发展，避免冒进"


# 全局实例
bazi_engine = BaziRuleEngine()
