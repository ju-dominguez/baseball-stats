# ctbl_scraper.py
import logging
from itertools import combinations
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

@dataclass
class ScraperConfig:
    base_url: str
    params: Dict[str, str]
    max_pages: int = 10

@dataclass
class StatsConfig:
    min_pa: int = 10
    woba_scale: float = 1.15

class CTBLScraper:
    def __init__(self, cfg: ScraperConfig):
        self.cfg = cfg
        self.session = requests.Session()

    def fetch(self) -> pd.DataFrame:
        records, headers = [], None
        for page in range(1, self.cfg.max_pages + 1):
            params = {**self.cfg.params}
            if page > 1:
                params["bpageNum"] = str(page)
            logger.info("Fetching page %d", page)
            resp = self.session.get(self.cfg.base_url, params=params)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            table = soup.find("table")
            if not table:
                break

            rows = table.find_all("tr")
            if headers is None:
                headers = [th.get_text(strip=True) for th in table.find_all("th")] \
                          or [td.get_text(strip=True) for td in rows[0].find_all("td")]

            for tr in rows[1:]:
                vals = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(vals) == len(headers):
                    records.append(vals)

            # stop if no data rows
            if not any(len(r.find_all("td")) == len(headers) for r in rows[1:]):
                break

        logger.info("Fetched %d rows", len(records))
        return pd.DataFrame(records, columns=headers)

class StatsProcessor:
    def __init__(self, cfg: StatsConfig):
        self.cfg = cfg

    def clean(self, df: pd.DataFrame, identity_cols=None) -> pd.DataFrame:
        if identity_cols is None:
            identity_cols = ["Name", "Team"]
        df2 = df.replace({"-": 0, "": 0}).copy()
        for col in df2.columns:
            if col not in identity_cols:
                df2[col] = pd.to_numeric(df2[col], errors="coerce")
        return df2

    def compute(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
        df_clean = self.clean(df)
        m = df_clean.copy()
        # compute singles & TB
        m["1B"] = m["H"] - m["2B"] - m["3B"] - m["HR"]
        m["TB"] = m["1B"] + 2*m["2B"] + 3*m["3B"] + 4*m["HR"]

        # wOBA
        num = (0.69*m["BB"] + 0.72*m["HBP"] + 0.89*m["1B"]
             + 1.27*m["2B"] + 1.62*m["3B"] + 2.10*m["HR"])
        den = (m["AB"] + m["BB"] + m["HBP"]).replace(0, pd.NA)
        m["wOBA"] = num.div(den)

        league_woba = m.loc[m["PA"] >= self.cfg.min_pa, "wOBA"].mean()
        m["wRAA"] = ((m["wOBA"] - league_woba) / self.cfg.woba_scale) * m["PA"]

        # traditional
        m["AVG"] = m["H"].div(m["AB"].replace(0, pd.NA))
        m["OBP"] = m[["H","BB","HBP"]].sum(1).div(
                   m[["AB","BB","HBP"]].sum(1).replace(0, pd.NA))
        m["SLG"] = m["TB"].div(m["AB"].replace(0, pd.NA))
        m["OPS"] = m["OBP"] + m["SLG"]

        for col in ["AVG","OBP","SLG","OPS","wOBA","wRAA"]:
            m[col] = pd.to_numeric(m[col], errors="coerce").fillna(0)

        return m, league_woba

    @staticmethod
    def get_qualified(df: pd.DataFrame, min_pa: int) -> pd.DataFrame:
        return df[df["PA"] >= min_pa]

    @staticmethod
    def calculate_handedness_score(lineup: pd.DataFrame) -> int:
        bats = lineup["Bats"].tolist()
        score = count = 0
        prev = None
        for curr in bats:
            if curr == prev:
                count += 1
                score += 1 + (1 if count >= 2 else 0)
            else:
                count = 0
            prev = curr
        return score

    def optimize_lineup(
        self,
        lineup: pd.DataFrame,
        override_spots: Optional[Dict[str,int]] = None,
        max_offset: int = 2,
        max_perf_drop: float = 0.05
    ) -> pd.DataFrame:
        if override_spots is None:
            override_spots = {}
        best = lineup.copy()
        best_score = self.calculate_handedness_score(best)
        improved = True

        while improved:
            improved = False
            for i, j in combinations(range(len(best)), 2):
                if (abs(i-j) > max_offset) or (i in override_spots.values()) or (j in override_spots.values()):
                    continue
                tmp = best.copy()
                tmp.iloc[[i,j]] = tmp.iloc[[j,i]].values
                perf_drop = (
                    abs(tmp.at[i,"batting_value"] - best.at[i,"batting_value"]) +
                    abs(tmp.at[j,"batting_value"] - best.at[j,"batting_value"])
                )
                sc = self.calculate_handedness_score(tmp)
                if sc < best_score and perf_drop <= max_perf_drop:
                    best, best_score, improved = tmp, sc, True
                    break

        return best
