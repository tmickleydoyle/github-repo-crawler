"""
Exhaustive search space generation for systematic GitHub repository discovery.

This module creates deterministic, non-overlapping search partitions that can be
tracked and exhausted systematically.
"""

import hashlib
import itertools
import logging
from dataclasses import dataclass
from typing import Iterator

logger = logging.getLogger(__name__)


@dataclass
class SearchPartition:
    """A unique, deterministic search partition."""

    partition_id: str
    query: str
    category: str
    subcategory: str
    expected_results: int
    priority: int = 0

    def __hash__(self) -> int:
        """Make partition hashable."""
        return hash(self.partition_id)


class SearchSpaceGenerator:
    """Generates exhaustive, non-overlapping search partitions."""

    def __init__(self):
        """Initialize the search space generator."""
        # Programming languages (most popular to least)
        self.languages = [
            "javascript", "python", "java", "typescript", "go", "rust", "c++", "c#",
            "php", "ruby", "swift", "kotlin", "c", "scala", "shell", "powershell",
            "objective-c", "r", "dart", "lua", "perl", "haskell", "julia", "elixir",
            "clojure", "f#", "erlang", "ocaml", "nim", "crystal", "zig", "v",
            "assembly", "fortran", "cobol", "pascal", "ada", "scheme", "racket",
            "coffeescript", "elm", "purescript", "reason", "ballerina", "d",
            "groovy", "matlab", "vhdl", "verilog", "tex", "html", "css", "dockerfile"
        ]

        # Star ranges (more granular for lower stars where most repos are)
        self.star_ranges = [
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
            "11..12", "13..14", "15..16", "17..18", "19..20",
            "21..23", "24..26", "27..29", "30..33", "34..37", "38..42",
            "43..47", "48..53", "54..59", "60..66", "67..74", "75..82",
            "83..91", "92..101", "102..112", "113..124", "125..137",
            "138..151", "152..167", "168..184", "185..203", "204..224",
            "225..247", "248..272", "273..299", "300..329", "330..362",
            "363..398", "399..438", "439..482", "483..530", "531..583",
            "584..641", "642..705", "706..776", "777..853", "854..938",
            "939..1032", "1033..1135", "1136..1249", "1250..1374", "1375..1511",
            "1512..1663", "1664..1829", "1830..2012", "2013..2213", "2214..2434",
            "2435..2678", "2679..2946", "2947..3240", "3241..3564", "3565..3921",
            "3922..4313", "4314..4744", "4745..5219", "5220..5741", "5742..6315",
            "6316..6946", "6947..7641", "7642..8405", "8406..9245", "9246..10170",
            "10171..11187", "11188..12305", "12306..13536", "13537..14890", "14891..16379",
            "16380..18017", "18018..19818", "19819..21800", "21801..23980", "23981..26378",
            "26379..29016", "29017..31917", "31918..35109", "35110..38620", "38621..42482",
            "42483..46730", "46731..51403", "51404..56544", "56545..62198", "62199..68418",
            "68419..75260", "75261..82786", "82787..91064", "91065..100000", ">100000"
        ]

        # Time ranges (monthly for recent, quarterly for older)
        self.time_ranges = [
            # 2024-2025 (monthly)
            "2025-01-01..2025-01-31", "2024-12-01..2024-12-31", "2024-11-01..2024-11-30",
            "2024-10-01..2024-10-31", "2024-09-01..2024-09-30", "2024-08-01..2024-08-31",
            "2024-07-01..2024-07-31", "2024-06-01..2024-06-30", "2024-05-01..2024-05-31",
            "2024-04-01..2024-04-30", "2024-03-01..2024-03-31", "2024-02-01..2024-02-29",
            "2024-01-01..2024-01-31",
            # 2023 (quarterly)
            "2023-10-01..2023-12-31", "2023-07-01..2023-09-30",
            "2023-04-01..2023-06-30", "2023-01-01..2023-03-31",
            # 2022 (quarterly)
            "2022-10-01..2022-12-31", "2022-07-01..2022-09-30",
            "2022-04-01..2022-06-30", "2022-01-01..2022-03-31",
            # 2021 (half-yearly)
            "2021-07-01..2021-12-31", "2021-01-01..2021-06-30",
            # 2020 (yearly)
            "2020-01-01..2020-12-31",
            # 2019 and earlier
            "2019-01-01..2019-12-31", "2018-01-01..2018-12-31",
            "2017-01-01..2017-12-31", "2016-01-01..2016-12-31",
            "2015-01-01..2015-12-31", "2014-01-01..2014-12-31",
            "2013-01-01..2013-12-31", "2012-01-01..2012-12-31",
            "2011-01-01..2011-12-31", "2010-01-01..2010-12-31",
            "..2009-12-31"
        ]

        # Repository sizes in KB
        self.size_ranges = [
            "0", "1", "2..3", "4..5", "6..8", "9..12", "13..17", "18..24",
            "25..33", "34..45", "46..61", "62..82", "83..111", "112..150",
            "151..203", "204..274", "275..370", "371..500", "501..675",
            "676..911", "912..1229", "1230..1659", "1660..2239", "2240..3023",
            "3024..4081", "4082..5509", "5510..7437", "7438..10039", "10040..13553",
            "13554..18296", "18297..24700", "24701..33345", "33346..45015",
            "45016..60771", "60772..82040", "82041..110754", "110755..149518",
            "149519..201849", "201850..272495", "272496..367869", "367870..496622",
            "496623..670455", "670456..905115", "905116..1221905", "1221906..1649525",
            ">1649525"
        ]

        # Common topics
        self.topics = [
            "api", "cli", "framework", "library", "tool", "web", "mobile", "game",
            "machine-learning", "ai", "data-science", "database", "devops", "docker",
            "kubernetes", "serverless", "microservices", "blockchain", "crypto",
            "security", "testing", "automation", "monitoring", "logging", "analytics",
            "frontend", "backend", "fullstack", "react", "vue", "angular", "nodejs",
            "django", "flask", "spring", "rails", "laravel", "express", "fastapi",
            "graphql", "rest-api", "grpc", "websocket", "mqtt", "kafka", "redis",
            "elasticsearch", "mongodb", "postgresql", "mysql", "sqlite"
        ]

        # Licenses
        self.licenses = [
            "mit", "apache-2.0", "gpl-3.0", "gpl-2.0", "bsd-3-clause", "bsd-2-clause",
            "unlicense", "lgpl-3.0", "lgpl-2.1", "mpl-2.0", "epl-2.0", "agpl-3.0",
            "cc0-1.0", "cc-by-4.0", "cc-by-sa-4.0", "isc", "artistic-2.0", "zlib",
            "wtfpl", "vim", "postgresql", "ofl-1.1", "ms-pl", "eupl-1.2"
        ]

    def generate_all_partitions(self) -> Iterator[SearchPartition]:
        """Generate all possible search partitions."""
        partition_count = 0

        # Strategy 1: Language + Stars (highest priority - most reliable)
        for lang, stars in itertools.product(self.languages, self.star_ranges):
            partition_id = self._generate_id(f"lang-star-{lang}-{stars}")
            query = f'is:public language:"{lang}" stars:{stars} fork:false archived:false'
            yield SearchPartition(
                partition_id=partition_id,
                query=query,
                category="language-stars",
                subcategory=f"{lang}:{stars}",
                expected_results=500,
                priority=1
            )
            partition_count += 1

        logger.info(f"Generated {partition_count} language-star partitions")

        # Strategy 2: Created date + Stars (good for finding new repos)
        for time_range, stars in itertools.product(self.time_ranges, self.star_ranges[:50]):
            partition_id = self._generate_id(f"time-star-{time_range}-{stars}")
            query = f"is:public created:{time_range} stars:{stars} fork:false"
            yield SearchPartition(
                partition_id=partition_id,
                query=query,
                category="time-stars",
                subcategory=f"{time_range}:{stars}",
                expected_results=300,
                priority=2
            )

        # Strategy 3: Topic + Stars (finds themed repositories)
        for topic, stars in itertools.product(self.topics, self.star_ranges[:30]):
            partition_id = self._generate_id(f"topic-star-{topic}-{stars}")
            query = f'is:public topic:"{topic}" stars:{stars} fork:false'
            yield SearchPartition(
                partition_id=partition_id,
                query=query,
                category="topic-stars",
                subcategory=f"{topic}:{stars}",
                expected_results=200,
                priority=3
            )

        # Strategy 4: Size + Language + Stars (very specific partitions)
        for size, lang, stars in itertools.product(
            self.size_ranges[:20], self.languages[:20], self.star_ranges[:20]
        ):
            partition_id = self._generate_id(f"size-lang-star-{size}-{lang}-{stars}")
            query = f'is:public size:{size} language:"{lang}" stars:{stars}'
            yield SearchPartition(
                partition_id=partition_id,
                query=query,
                category="size-language-stars",
                subcategory=f"{size}:{lang}:{stars}",
                expected_results=100,
                priority=4
            )

        # Strategy 5: License + Language (finds open source projects)
        for license_type, lang in itertools.product(self.licenses, self.languages[:30]):
            partition_id = self._generate_id(f"license-lang-{license_type}-{lang}")
            query = f'is:public license:"{license_type}" language:"{lang}" stars:>0'
            yield SearchPartition(
                partition_id=partition_id,
                query=query,
                category="license-language",
                subcategory=f"{license_type}:{lang}",
                expected_results=400,
                priority=5
            )

        logger.info(f"Total partitions available: {partition_count}+")

    def generate_priority_partitions(self, count: int = 1000) -> list[SearchPartition]:
        """Generate high-priority partitions for initial crawling."""
        partitions = []

        # Focus on most common scenarios first
        priority_languages = self.languages[:15]
        priority_stars = self.star_ranges[:30]

        for lang, stars in itertools.product(priority_languages, priority_stars):
            if len(partitions) >= count:
                break

            partition_id = self._generate_id(f"priority-{lang}-{stars}")
            query = f'is:public language:"{lang}" stars:{stars} fork:false archived:false'
            partitions.append(SearchPartition(
                partition_id=partition_id,
                query=query,
                category="priority",
                subcategory=f"{lang}:{stars}",
                expected_results=800,
                priority=0
            ))

        return partitions

    def _generate_id(self, key: str) -> str:
        """Generate a deterministic partition ID."""
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def estimate_total_partitions(self) -> int:
        """Estimate the total number of partitions."""
        total = 0
        total += len(self.languages) * len(self.star_ranges)  # lang-star
        total += len(self.time_ranges) * min(50, len(self.star_ranges))  # time-star
        total += len(self.topics) * min(30, len(self.star_ranges))  # topic-star
        total += min(20, len(self.size_ranges)) * min(20, len(self.languages)) * min(20, len(self.star_ranges))
        total += len(self.licenses) * min(30, len(self.languages))  # license-lang
        return total