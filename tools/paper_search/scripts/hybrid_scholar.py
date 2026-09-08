#!/usr/bin/env python3
"""
Hybrid Scholar — OpenAlex 学术检索 + Crossref DOI 核验

基于 OpenAlex 开放学术数据源检索论文，对结果做标题去重与查询相关性
排序，再用 Crossref 核验 DOI 元数据，输出可追溯的论文引用信息。
"""

import argparse
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import urllib.error
import urllib.parse
import urllib.request

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from openalex_scholar import OpenAlexScholar
from scholar_models import Paper

_SKILL_ROOT = Path(__file__).resolve().parents[3]
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from tools.common.io_utils import configure_stdio

configure_stdio()


# ---------------------------------------------------------------------------
# 搜索结果数据类
# ---------------------------------------------------------------------------

class CrossrefLookupError(RuntimeError):
    """Crossref 查询失败。"""


@dataclass
class CrossrefMetadata:
    """Crossref 返回的可用于引用核验的元数据。"""

    doi: str
    title: str
    authors: List[str]
    citation_authors: List[str]
    author_families: List[str]
    year: Optional[int]
    venue: Optional[str]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    url: Optional[str]
    work_type: Optional[str] = None
    publisher: Optional[str] = None
    publisher_location: Optional[str] = None
    event_name: Optional[str] = None
    event_location: Optional[str] = None
    event_date: Optional[str] = None
    published_date: Optional[str] = None
    updated_date: Optional[str] = None
    standard_number: Optional[str] = None
    patent_country: Optional[str] = None
    patent_number: Optional[str] = None


@dataclass
class CrossrefValidation:
    """单篇论文的自动核验结果。"""

    verified: bool
    metadata: Optional[CrossrefMetadata]
    issues: List[str] = field(default_factory=list)


def _normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    value = doi.strip()
    value = re.sub(r"^https?://doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    return value.rstrip(" .")


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(
        re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", value.lower()).split()
    )


def _titles_match(left: str, right: str) -> bool:
    """允许标点、大小写和少量题名差异，不接受主题完全不同。"""
    left_normalized = _normalize_text(left)
    right_normalized = _normalize_text(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True

    ratio = difflib.SequenceMatcher(
        None, left_normalized, right_normalized
    ).ratio()
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    overlap = len(left_tokens & right_tokens) / max(
        len(left_tokens | right_tokens), 1
    )
    return ratio >= 0.86 or overlap >= 0.90


def _family_from_display_name(name: str) -> str:
    parts = name.strip().split()
    return parts[-1].lower() if parts else ""


def _gbt_author(family: str, given: str) -> str:
    """生成常用的 GB/T 7714 英文作者写法：Family Given-initials。"""
    family = " ".join(family.split()).strip()
    given_parts = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", given or "")
    initials = " ".join(part[0].upper() for part in given_parts if part)
    return " ".join(part for part in (family, initials) if part)


def _fallback_gbt_author(name: str) -> str:
    parts = name.strip().split()
    if len(parts) < 2:
        return name.strip()
    return _gbt_author(parts[-1], " ".join(parts[:-1]))


WORK_TYPE_TO_GBT = {
    "journal-article": "J",
    "proceedings-article": "C",
    "book": "M",
    "book-chapter": "M",
    "book-section": "M",
    "book-part": "M",
    "monograph": "M",
    "dissertation": "D",
    "report": "R",
    "standard": "S",
    "patent": "P",
    "dataset": "DS/OL",
    "posted-content": "EB/OL",
}


class CrossrefValidator:
    """通过 Crossref DOI 元数据核验 OpenAlex 候选文献。"""

    def __init__(self, email: Optional[str] = None, timeout: int = 15):
        self.base_url = "https://api.crossref.org/works"
        self.email = email
        self.timeout = timeout

    def validate(self, paper: "HybridPaper") -> CrossrefValidation:
        doi = _normalize_doi(paper.doi)
        if not doi:
            return CrossrefValidation(False, None, ["缺少 DOI，无法自动核验"])

        try:
            metadata = self.fetch(doi)
        except CrossrefLookupError as exc:
            return CrossrefValidation(False, None, [str(exc)])

        issues: List[str] = []
        if _normalize_doi(metadata.doi) != doi:
            return CrossrefValidation(False, metadata, ["Crossref 返回的 DOI 不一致"])
        if not _titles_match(paper.title, metadata.title):
            return CrossrefValidation(
                False,
                metadata,
                ["OpenAlex 与 Crossref 题名不一致"],
            )

        if paper.authors and metadata.author_families:
            openalex_family = _family_from_display_name(paper.authors[0])
            crossref_family = metadata.author_families[0].lower()
            if openalex_family != crossref_family:
                return CrossrefValidation(
                    False,
                    metadata,
                    ["OpenAlex 与 Crossref 首位作者不一致"],
                )

        if paper.year and metadata.year and paper.year != metadata.year:
            if abs(paper.year - metadata.year) > 1:
                return CrossrefValidation(
                    False,
                    metadata,
                    [f"OpenAlex 与 Crossref 年份不一致：{paper.year} / {metadata.year}"],
                )
            issues.append(
                f"年份存在在线发表与正式出版差异：{paper.year} / {metadata.year}"
            )

        missing_fields = []
        if metadata.year is None:
            missing_fields.append("年份")
        reference_type = WORK_TYPE_TO_GBT.get(metadata.work_type or "")
        if reference_type is None:
            missing_fields.append("文献类型")
        elif reference_type != "S" and not metadata.authors:
            missing_fields.append("作者/申请者")
        elif reference_type == "J" and not metadata.venue:
            missing_fields.append("期刊")
        elif reference_type == "C":
            if not metadata.venue:
                missing_fields.append("论文集")
            if not metadata.event_location:
                missing_fields.append("会议地点")
            if not metadata.event_date:
                missing_fields.append("会议日期")
        elif reference_type in {"M", "D", "R"}:
            if metadata.work_type in {"book-chapter", "book-section", "book-part"}:
                if not metadata.venue:
                    missing_fields.append("图书题名")
            if not metadata.publisher_location:
                missing_fields.append("出版地")
            if not metadata.publisher:
                missing_fields.append("出版社/出版者")
        elif reference_type == "S":
            if not metadata.standard_number:
                missing_fields.append("标准号")
            if not metadata.publisher_location:
                missing_fields.append("出版地")
            if not metadata.publisher:
                missing_fields.append("出版者")
        elif reference_type == "P":
            if not metadata.patent_country:
                missing_fields.append("专利国别")
            if not metadata.patent_number:
                missing_fields.append("专利号")
            if not metadata.published_date:
                missing_fields.append("公告/公开日期")
        elif reference_type in {"DS/OL", "EB/OL"} and not metadata.url:
            missing_fields.append("获取路径")
        if missing_fields:
            return CrossrefValidation(
                False,
                metadata,
                [f"书目信息不完整：缺少{'、'.join(missing_fields)}"],
            )

        return CrossrefValidation(True, metadata, issues)

    def fetch(self, doi: str) -> CrossrefMetadata:
        normalized_doi = _normalize_doi(doi)
        if not normalized_doi:
            raise CrossrefLookupError("DOI 格式为空，无法查询 Crossref")

        url = f"{self.base_url}/{urllib.parse.quote(normalized_doi, safe='')}"
        if self.email:
            url = f"{url}?{urllib.parse.urlencode({'mailto': self.email})}"

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    f"mathmodel-paper-search/1.0 (mailto:{self.email})"
                    if self.email
                    else "mathmodel-paper-search/1.0"
                )
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise CrossrefLookupError(f"Crossref 未找到 DOI：{normalized_doi}") from exc
            raise CrossrefLookupError(
                f"Crossref 请求失败（HTTP {exc.code}）：{exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise CrossrefLookupError(f"Crossref 网络请求失败：{exc.reason}") from exc
        except TimeoutError as exc:
            raise CrossrefLookupError("Crossref 请求超时") from exc
        except json.JSONDecodeError as exc:
            raise CrossrefLookupError("Crossref 返回数据格式异常") from exc

        message = payload.get("message") or {}
        return self._parse_message(message, normalized_doi)

    @staticmethod
    def _parse_message(message: Dict[str, Any], fallback_doi: str) -> CrossrefMetadata:
        titles = message.get("title") or []
        title = titles[0].strip() if titles and titles[0] else ""
        if not title:
            raise CrossrefLookupError("Crossref 元数据缺少题名")

        authors: List[str] = []
        citation_authors: List[str] = []
        author_families: List[str] = []
        for author in message.get("author") or []:
            family = str(author.get("family") or "").strip()
            given = str(author.get("given") or "").strip()
            if not family and not given:
                continue
            display_name = " ".join(part for part in (given, family) if part)
            authors.append(display_name)
            citation_authors.append(_gbt_author(family, given) or display_name)
            if family:
                author_families.append(family)

        def date_year(key: str) -> Optional[int]:
            parts = (message.get(key) or {}).get("date-parts") or []
            if not parts or not parts[0]:
                return None
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                return None

        def date_text(key: str) -> Optional[str]:
            parts = (message.get(key) or {}).get("date-parts") or []
            if not parts or not parts[0]:
                return None
            values = parts[0]
            try:
                year_value = int(values[0])
                if len(values) >= 3:
                    return f"{year_value:04d}-{int(values[1]):02d}-{int(values[2]):02d}"
                if len(values) == 2:
                    return f"{year_value:04d}-{int(values[1]):02d}"
                return str(year_value)
            except (TypeError, ValueError):
                return None

        year = (
            date_year("published-print")
            or date_year("published-online")
            or date_year("issued")
        )
        published_date = (
            date_text("published-print")
            or date_text("published-online")
            or date_text("issued")
        )
        updated_date = date_text("updated")
        biblio_url = message.get("URL") or f"https://doi.org/{fallback_doi}"
        container_titles = message.get("container-title") or []
        event = message.get("event") or {}
        event_start = event.get("start") or {}
        event_start_parts = event_start.get("date-parts") or []
        event_date = None
        if event_start_parts and event_start_parts[0]:
            parts = event_start_parts[0]
            try:
                if len(parts) >= 3:
                    event_date = (
                        f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                    )
                elif len(parts) == 2:
                    event_date = f"{int(parts[0]):04d}-{int(parts[1]):02d}"
                else:
                    event_date = str(int(parts[0]))
            except (TypeError, ValueError):
                event_date = None
        return CrossrefMetadata(
            doi=_normalize_doi(str(message.get("DOI") or fallback_doi)) or fallback_doi,
            title=title,
            authors=authors,
            citation_authors=citation_authors,
            author_families=author_families,
            year=year,
            venue=container_titles[0] if container_titles else None,
            volume=str(message["volume"]) if message.get("volume") else None,
            issue=str(message["issue"]) if message.get("issue") else None,
            pages=str(message["page"]) if message.get("page") else None,
            url=biblio_url,
            work_type=str(message.get("type") or "") or None,
            publisher=str(message.get("publisher") or "") or None,
            publisher_location=str(message.get("publisher-location") or "") or None,
            event_name=str(event.get("name") or "") or None,
            event_location=str(event.get("location") or "") or None,
            event_date=event_date,
            published_date=published_date,
            updated_date=updated_date,
            standard_number=(
                str(message.get("number") or message.get("standard-number") or "") or None
            ),
            patent_country=str(
                message.get("jurisdiction") or message.get("country") or ""
            ) or None,
            patent_number=str(
                message.get("number") or message.get("article-number") or ""
            ) or None,
        )


@dataclass
class HybridPaper:
    """融合论文（带来源追踪）"""
    title: str
    authors: List[str]
    year: Optional[int]
    citations: int
    doi: Optional[str]
    abstract: Optional[str]
    sources: List[str] = field(default_factory=list)
    venue: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    url: Optional[str] = None
    citation_authors: List[str] = field(default_factory=list)
    verification_status: str = "unverified"
    verification_issues: List[str] = field(default_factory=list)
    work_type: Optional[str] = None
    publisher: Optional[str] = None
    publisher_location: Optional[str] = None
    event_name: Optional[str] = None
    event_location: Optional[str] = None
    event_date: Optional[str] = None
    published_date: Optional[str] = None
    updated_date: Optional[str] = None
    standard_number: Optional[str] = None
    patent_country: Optional[str] = None
    patent_number: Optional[str] = None

    @property
    def citation_ready(self) -> bool:
        """书目信息已通过自动核验，可直接写入参考文献。"""
        common_ready = (
            self.verification_status == "crossref_verified"
            and bool(self.title)
            and (bool(self.authors) or self.reference_type == "S")
            and bool(self.year)
            and bool(self.doi)
            and self.reference_type is not None
        )
        if not common_ready:
            return False
        if self.reference_type == "J":
            return bool(self.venue)
        if self.reference_type == "C":
            return bool(self.venue and self.event_location and self.event_date)
        if self.reference_type in {"M", "D", "R"}:
            return bool(self.publisher_location and self.publisher)
        if self.reference_type == "S":
            return bool(
                self.standard_number
                and self.publisher_location
                and self.publisher
            )
        if self.reference_type == "P":
            return bool(
                self.patent_country
                and self.patent_number
                and self.published_date
                and self.url
            )
        if self.reference_type in {"DS/OL", "EB/OL"}:
            return bool(self.url)
        return False

    @property
    def reference_type(self) -> Optional[str]:
        return WORK_TYPE_TO_GBT.get(self.work_type or "")

    @property
    def citation_format(self) -> Optional[str]:
        """生成可粘贴到论文参考文献的 GB/T 7714 条目。"""
        if not self.citation_ready:
            return None
        authors = self.citation_authors or [
            _fallback_gbt_author(author) for author in self.authors
        ]
        author_text = ", ".join(authors[:3])
        if len(authors) > 3:
            author_text += ", et al"

        title = self.title.rstrip("。.!?？")
        prefix = (
            f"{author_text}. {title}[{self.reference_type}]."
            if author_text
            else f"{title}[{self.reference_type}]."
        )
        reference_type = self.reference_type

        if reference_type == "J":
            entry = prefix
            if self.venue:
                entry += f" {self.venue},"
            if self.year:
                entry += f" {self.year},"
            if self.volume:
                entry += f" {self.volume}"
                if self.issue:
                    entry += f"({self.issue})"
            elif self.issue:
                entry += f" ({self.issue})"
            if self.pages:
                entry += f": {self.pages}"
        elif reference_type == "C":
            parts = [self.venue, self.event_location, self.event_date]
            entry = prefix.replace(f"[{reference_type}].", f"[{reference_type}]//")
            entry += ", ".join(part for part in parts if part)
            if self.pages:
                entry += f": {self.pages}"
        elif reference_type in {"M", "D", "R"}:
            if self.work_type in {"book-chapter", "book-section", "book-part"}:
                entry = prefix.replace("[M].", "[M]//")
                if self.venue:
                    entry += f"{self.venue}."
            else:
                entry = prefix
            place_publisher = ": ".join(
                part for part in (self.publisher_location, self.publisher) if part
            )
            if place_publisher:
                entry += f" {place_publisher},"
            if self.year:
                entry += f" {self.year}"
        elif reference_type == "S":
            standard_number = self.standard_number or ""
            entry = f"{standard_number}. {title}[S]."
            place_publisher = ": ".join(
                part for part in (self.publisher_location, self.publisher) if part
            )
            if place_publisher:
                entry += f" {place_publisher},"
            if self.year:
                entry += f" {self.year}"
        elif reference_type == "P":
            entry = prefix.replace(
                f"[{reference_type}].",
                f": {self.patent_country}, {self.patent_number}[{reference_type}].",
            )
            if self.published_date:
                entry += f" {self.published_date}."
            if self.url:
                entry += f" {self.url}"
        else:
            entry = prefix
            if self.publisher_location and self.publisher:
                entry += f" {self.publisher_location}: {self.publisher},"
            if self.year:
                entry += f" {self.year}"
            if self.updated_date:
                entry += f" ({self.updated_date})"
            if self.url:
                entry += f". {self.url}"

        if self.doi and reference_type not in {"P", "DS/OL", "EB/OL"}:
            entry += f". DOI: {_normalize_doi(self.doi)}"
        return entry.rstrip(" .") + "."

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "citations": self.citations,
            "doi": self.doi,
            "abstract": self.abstract,
            "sources": self.sources,
            "citation_format": self.citation_format,
            "verification_status": self.verification_status,
            "verification_issues": self.verification_issues,
            "citation_ready": self.citation_ready,
            "reference_type": self.reference_type,
            "venue": self.venue,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "url": self.url,
            "publisher": self.publisher,
            "publisher_location": self.publisher_location,
            "event_name": self.event_name,
            "event_location": self.event_location,
            "event_date": self.event_date,
            "published_date": self.published_date,
            "updated_date": self.updated_date,
            "standard_number": self.standard_number,
            "patent_country": self.patent_country,
            "patent_number": self.patent_number,
        }


# ---------------------------------------------------------------------------
# Hybrid Scholar
# ---------------------------------------------------------------------------

class HybridScholar:
    """OpenAlex 检索、相关性排序与 Crossref DOI 核验器。"""

    def __init__(
        self,
        email: Optional[str] = None,
        timeout: int = 15,
    ):
        self.openalex = OpenAlexScholar(email=email)
        self.crossref = CrossrefValidator(email=email, timeout=timeout)

    def search_papers(
        self,
        query: str,
        limit: int = 8,
        sort: str = "relevance",
        min_citations: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        field_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        OpenAlex 检索 + 去重 + 相关性排序。

        Args:
            query: 搜索关键词
            limit: 最终返回结果数量
            sort: 排序方式（OpenAlex）
            min_citations: 最低引用量
            year_from / year_to: 年份范围
            field_filter: 领域过滤

        Returns:
            {
                "verified": [...],          # 已通过 Crossref 核验
                "papers": [...],            # 当前查询的全部结果
                "stats": {...},
            }
        """
        if limit < 1:
            raise ValueError("limit 必须大于 0")

        self._current_query = query
        # 多取一些以便去重与相关性过滤后仍能补足名额
        fetch_limit = max(limit * 2, 15)
        oa_papers = self.openalex.search_papers(
            query, limit=fetch_limit, sort=sort,
            min_citations=min_citations,
            year_from=year_from, year_to=year_to,
            field_filter=field_filter,
        ) or []

        return self._fuse(oa_papers, final_limit=limit)

    # ------------------------------------------------------------------
    # 去重 / 相关性排序
    # ------------------------------------------------------------------

    def _fuse(
        self,
        oa_papers: List[Paper],
        final_limit: int,
    ) -> Dict[str, Any]:
        """将 OpenAlex 结果转为 HybridPaper，去重并按相关性排序。"""
        papers: List[HybridPaper] = []
        for p in oa_papers:
            papers.append(HybridPaper(
                title=p.title,
                authors=p.authors,
                year=p.publication_year,
                citations=p.cited_by_count,
                doi=p.doi,
                abstract=p.abstract,
                sources=["openalex"],
                venue=p.venue,
                volume=p.volume,
                issue=p.issue,
                pages=p.pages,
                url=p.url,
            ))

        # Step 1 — 按查询词覆盖率过滤，再以相关性优先、引用量次优排序。
        terms = self._query_terms(self._current_query)
        before_filter = len(papers)
        papers = [paper for paper in papers if self._is_relevant(paper, terms)]
        filtered_irrelevant = before_filter - len(papers)

        # Step 2 — 标题规范化去重，优先保留引用/摘要/出处更完整的记录。
        before_dedup = len(papers)
        papers = self._dedup_titles(papers)
        collapsed_duplicates = before_dedup - len(papers)

        rank = lambda paper: (self._relevance_score(paper, terms), paper.citations)
        papers.sort(key=rank, reverse=True)

        selected: List[HybridPaper] = []
        verified: List[HybridPaper] = []
        for paper in papers:
            self._verify_paper(paper)
            selected.append(paper)
            if paper.citation_ready:
                verified.append(paper)
            if len(verified) >= final_limit:
                break

        return {
            "query": self._current_query,
            "verified": verified,
            "papers": selected,
            "stats": {
                "openalex_total": len(oa_papers),
                "citation_ready": len(verified),
                "openalex_unique": len(papers),
                "filtered_irrelevant": filtered_irrelevant,
                "collapsed_duplicates": collapsed_duplicates,
                "verification_attempted": len(selected),
                "verification_failed": len(selected) - len(verified),
            },
            "verification": {
                "source": "crossref",
                "direct_citation_requires": "citation_ready",
            },
        }

    def _verify_paper(self, paper: HybridPaper) -> None:
        result = self.crossref.validate(paper)
        paper.verification_issues = result.issues
        if not result.verified or result.metadata is None:
            paper.verification_status = "unverified"
            return

        metadata = result.metadata
        paper.title = metadata.title
        paper.authors = metadata.authors or paper.authors
        paper.citation_authors = metadata.citation_authors
        paper.year = metadata.year or paper.year
        paper.doi = metadata.doi or paper.doi
        paper.venue = metadata.venue or paper.venue
        paper.volume = metadata.volume or paper.volume
        paper.issue = metadata.issue or paper.issue
        paper.pages = metadata.pages or paper.pages
        paper.url = metadata.url or paper.url
        paper.work_type = metadata.work_type
        paper.publisher = metadata.publisher
        paper.publisher_location = metadata.publisher_location
        paper.event_name = metadata.event_name
        paper.event_location = metadata.event_location
        paper.event_date = metadata.event_date
        paper.published_date = metadata.published_date
        paper.updated_date = metadata.updated_date
        paper.standard_number = metadata.standard_number
        paper.patent_country = metadata.patent_country
        paper.patent_number = metadata.patent_number
        paper.sources = list(dict.fromkeys([*paper.sources, "crossref"]))
        paper.verification_status = "crossref_verified"

    @staticmethod
    def _normalized_title(title: str) -> str:
        return " ".join(re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", title.lower()).split())

    @classmethod
    def _dedup_titles(cls, papers: List[HybridPaper]) -> List[HybridPaper]:
        chosen: Dict[str, HybridPaper] = {}
        for paper in papers:
            key = cls._normalized_title(paper.title) or paper.doi or paper.url or str(id(paper))
            current = chosen.get(key)
            if current is None or (paper.citations, bool(paper.abstract), bool(paper.venue)) > (
                current.citations, bool(current.abstract), bool(current.venue)
            ):
                chosen[key] = paper
        return list(chosen.values())

    @staticmethod
    def _query_terms(query: str) -> List[str]:
        """提取具有检索意义的词；连字符术语同时按组成词匹配。"""
        stopwords = {
            "a", "an", "and", "for", "in", "of", "on", "or", "the", "to", "with",
            "analysis", "based", "method", "model", "study", "using",
        }
        normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", query.lower())
        return [term for term in normalized.split() if term not in stopwords and len(term) > 1]

    @staticmethod
    def _paper_text(paper: HybridPaper) -> tuple[str, str]:
        title = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", paper.title.lower())
        detail = " ".join(filter(None, [paper.abstract, paper.venue])).lower()
        detail = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", detail)
        return f" {title} ", f" {detail} "

    @classmethod
    def _matched_terms(cls, paper: HybridPaper, terms: List[str]) -> Set[str]:
        title, detail = cls._paper_text(paper)
        return {
            term for term in terms
            if f" {term} " in title or f" {term} " in detail
        }

    @classmethod
    def _is_relevant(cls, paper: HybridPaper, terms: List[str]) -> bool:
        # 单个词可能是 AHP、PCA 等缩写，无法仅凭字面覆盖率安全淘汰结果。
        if len(terms) < 2:
            return True
        required = min(2, len(terms))
        return len(cls._matched_terms(paper, terms)) >= required

    @classmethod
    def _relevance_score(cls, paper: HybridPaper, terms: List[str]) -> int:
        title, detail = cls._paper_text(paper)
        return sum(
            3 if f" {term} " in title else 1 if f" {term} " in detail else 0
            for term in terms
        )

    # ------------------------------------------------------------------
    # 展示
    # ------------------------------------------------------------------

    _current_query: str = ""

    def print_results(self, result: Dict[str, Any]):
        """打印检索结果。"""
        query = result.get("query", "")
        self._current_query = query  # stash for template
        stats = result["stats"]

        print("  数据源: OpenAlex（候选发现） + Crossref（DOI 核验）")
        print(f"  统计: OpenAlex {stats['openalex_total']} 篇 | "
              f"相关性过滤 {stats['filtered_irrelevant']} 篇 | "
              f"去重折叠 {stats['collapsed_duplicates']} 篇")
        print()

        selected = result.get("papers", [])
        verified = result.get("verified", [])
        unverified = [paper for paper in selected if not paper.citation_ready]
        if verified:
            self._print_section(
                "已核验，可直接写入参考文献",
                "✓",
                "OpenAlex + Crossref",
                verified,
                "verified",
            )
        if unverified:
            self._print_section(
                "候选文献，未通过自动核验",
                "◆",
                "未通过自动核验",
                unverified,
                "oa",
            )

        if not selected:
            print("  未找到相关论文。\n")

    _SECTION_COLORS = {
        "verified": "\033[33m",  # 金色
        "oa": "\033[36m",       # 青色
        "any": "\033[35m",      # 紫色
        "reset": "\033[0m",
    }
    # Windows 兼容：如果颜色不支持则静默降级
    _USE_COLOR = sys.platform != "win32" or os.environ.get("TERM", "").startswith("xterm")

    @classmethod
    def _c(cls, code: str) -> str:
        if cls._USE_COLOR:
            return cls._SECTION_COLORS.get(code, "")
        return ""

    def _print_section(self, title: str, icon: str, subtitle: str,
                       papers: List[HybridPaper], tag: str):
        c_tag = self._c(tag)
        c_reset = self._c("reset")

        print(f"  {c_tag}{icon} {title}{c_reset}")
        print(f"  {c_tag}  {subtitle}{c_reset}")
        print(f"  {c_tag}{'─' * 56}{c_reset}")

        for i, hp in enumerate(papers, 1):
            authors = ", ".join(hp.authors[:4])
            if len(hp.authors) > 4:
                authors += " et al."

            line = f"  [{i}] {hp.title}"
            print(f"  {c_tag}{line}{c_reset}")

            details = []
            if authors:
                details.append(f"作者: {authors}")
            if hp.year:
                details.append(f"年份: {hp.year}")
            if hp.citations:
                details.append(f"引用: {hp.citations}")
            if hp.doi:
                details.append(f"DOI: {hp.doi}")
            details.append(
                "核验: 已通过 Crossref"
                if hp.citation_ready
                else "核验: 未通过"
            )

            if details:
                print(f"     {' | '.join(details)}")
            if hp.abstract:
                preview = hp.abstract[:120].replace("\n", " ")
                print(f"     摘要: {preview}...")
            if hp.citation_ready:
                print(f"     GB/T 7714: {hp.citation_format}")
            if hp.verification_issues:
                print(f"     核验提示: {'；'.join(hp.verification_issues)}")
            print()

        print()

    def results_to_json(self, result: Dict[str, Any]) -> str:
        """输出为 JSON。"""
        return json.dumps(result, ensure_ascii=False, indent=2,
                          default=self._json_default)

    @staticmethod
    def _json_default(obj):
        if isinstance(obj, HybridPaper):
            return obj.to_dict()
        if isinstance(obj, Paper):
            return obj.to_dict()
        return str(obj)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hybrid Scholar — OpenAlex 检索 + Crossref DOI 核验 + GB/T 7714 输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 混合搜索（默认）
  python hybrid_scholar.py --query "grey prediction model"

  # 高级过滤
  python hybrid_scholar.py --query "TOPSIS" --min-citations 10 --year-from 2020 --field mathematics

  # JSON 输出
  python hybrid_scholar.py --query "LSTM" --json
        """,
    )
    parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    parser.add_argument("--limit", "-n", type=int, default=8,
                        help="最终返回结果数量（默认 8）")
    parser.add_argument("--email", "-e",
                        help="OpenAlex 礼貌池邮箱（建议填写真实邮箱）")
    parser.add_argument("--sort", "-s",
                        choices=["relevance", "cited_by_count:desc",
                                 "cited_by_count:asc", "publication_year:desc",
                                 "publication_year:asc"],
                        default="relevance",
                        help="排序方式（默认相关性）")
    parser.add_argument("--min-citations", type=int,
                        help="最低引用量过滤")
    parser.add_argument("--year-from", type=int,
                        help="起始年份")
    parser.add_argument("--year-to", type=int,
                        help="结束年份")
    parser.add_argument("--field",
                        choices=["mathematics", "computer_science", "engineering",
                                 "statistics", "operations_research", "physics", "economics"],
                        help="领域过滤")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以 JSON 格式输出")
    parser.add_argument("--append-to", type=Path, metavar="FILE",
                        help="将本次 JSON 结果追加到列表文件（隐含 --json）")
    return parser


def append_json_result(path: Path, payload: str) -> None:
    """Atomically append one query result to the audit JSON list."""
    existing = []
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            existing = json.load(stream)
        if not isinstance(existing, list):
            raise ValueError(f"追加文件顶层必须是 JSON 列表: {path}")
    existing.append(json.loads(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit 必须大于 0")
    if args.year_from is not None and args.year_to is not None and args.year_from > args.year_to:
        parser.error("--year-from 不能晚于 --year-to")

    scholar = HybridScholar(email=args.email)
    result = scholar.search_papers(
        query=args.query,
        limit=args.limit,
        sort=args.sort,
        min_citations=args.min_citations,
        year_from=args.year_from,
        year_to=args.year_to,
        field_filter=args.field,
    )

    if args.append_to:
        append_json_result(args.append_to, scholar.results_to_json(result))
    elif args.json:
        print(scholar.results_to_json(result))
    else:
        scholar.print_results(result)


if __name__ == "__main__":
    main()
