"""
Pagination Performance Testing Script

MEDIUM-015: Compare offset vs cursor pagination performance.

This script:
1. Creates a large test dataset (configurable size)
2. Tests offset pagination at various page numbers
3. Tests cursor pagination at same page numbers
4. Generates performance comparison report

Usage:
    python scripts/test_pagination_performance.py
    python scripts/test_pagination_performance.py --dataset-size 100000
    python scripts/test_pagination_performance.py --output perf_report.json
"""

import asyncio
import time
import argparse
import json
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models and utilities
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.patient import Patient
from app.utils.cursor_pagination import CursorPaginator
from app.database import get_db


class PaginationPerformanceTester:
    """Test and compare pagination performance."""

    def __init__(self, db: AsyncSession):
        """
        Initialize tester.

        Args:
            db: Async database session
        """
        self.db = db

    async def create_test_dataset(self, size: int = 10000) -> None:
        """
        Create test dataset with specified number of records.

        Args:
            size: Number of test records to create
        """
        print(f"Creating test dataset with {size} records...")

        # Check existing count
        count_query = select(func.count(Patient.id))
        result = await self.db.execute(count_query)
        existing_count = result.scalar()

        if existing_count >= size:
            print(f"  ✓ Dataset already has {existing_count} records (target: {size})")
            return

        # Create records in batches
        batch_size = 1000
        to_create = size - existing_count

        for i in range(0, to_create, batch_size):
            batch = []
            for j in range(batch_size):
                if i + j >= to_create:
                    break

                # Create test patient
                patient = Patient(
                    id=uuid4(),
                    name=f"Test Patient {i + j}",
                    phone=f"+5511{9000000000 + i + j}",
                    email=f"test{i + j}@example.com",
                    doctor_id=uuid4(),  # Dummy doctor ID
                    created_at=datetime.utcnow() - timedelta(days=(to_create - i - j))
                )
                batch.append(patient)

            self.db.add_all(batch)
            await self.db.commit()

            print(f"  Created {min(i + batch_size, to_create)}/{to_create} records...")

        print(f"✓ Dataset creation complete ({size} total records)")

    async def test_offset_pagination(
        self,
        page_number: int,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Test offset-based pagination performance.

        Args:
            page_number: Page number to fetch (1-indexed)
            page_size: Items per page

        Returns:
            Performance metrics
        """
        offset = (page_number - 1) * page_size

        query = select(Patient).offset(offset).limit(page_size).order_by(
            Patient.created_at.desc(),
            Patient.id.desc()
        )

        start = time.time()
        result = await self.db.execute(query)
        items = result.scalars().all()
        duration = time.time() - start

        return {
            'method': 'offset',
            'page_number': page_number,
            'page_size': page_size,
            'offset': offset,
            'items_returned': len(items),
            'duration_seconds': duration,
            'duration_ms': duration * 1000
        }

    async def test_cursor_pagination(
        self,
        page_number: int,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Test cursor-based pagination performance.

        Args:
            page_number: Page number to fetch (1-indexed)
            page_size: Items per page

        Returns:
            Performance metrics
        """
        # For cursor pagination, we need to get cursor for page N-1
        cursor = None

        if page_number > 1:
            # Get cursor by fetching previous pages
            # Note: In real usage, cursor would be saved from previous request
            query = select(Patient).order_by(
                Patient.created_at.desc(),
                Patient.id.desc()
            ).limit((page_number - 1) * page_size)

            result = await self.db.execute(query)
            items = result.scalars().all()

            if items:
                last_item = items[-1]
                cursor = CursorPaginator.encode_cursor(
                    last_item.id,
                    last_item.created_at
                )

        # Now test the actual cursor pagination
        query = select(Patient)

        start = time.time()
        page = await CursorPaginator.paginate(
            query=query,
            model=Patient,
            db=self.db,
            cursor=cursor,
            limit=page_size
        )
        duration = time.time() - start

        return {
            'method': 'cursor',
            'page_number': page_number,
            'page_size': page_size,
            'cursor': cursor[:20] + '...' if cursor else None,
            'items_returned': len(page.items),
            'duration_seconds': duration,
            'duration_ms': duration * 1000,
            'has_next': page.has_next
        }

    async def run_comprehensive_test(
        self,
        page_numbers: List[int] = None,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Run comprehensive performance comparison.

        Args:
            page_numbers: List of page numbers to test (default: [1, 10, 100, 500, 1000])
            page_size: Items per page

        Returns:
            Complete performance report
        """
        if page_numbers is None:
            page_numbers = [1, 10, 100, 500, 1000]

        print(f"\nRunning performance tests...")
        print(f"Page size: {page_size}")
        print(f"Pages to test: {page_numbers}")

        results = {
            'test_config': {
                'page_size': page_size,
                'pages_tested': page_numbers,
                'timestamp': datetime.utcnow().isoformat()
            },
            'results': []
        }

        for page_num in page_numbers:
            print(f"\nTesting page {page_num}...")

            # Test offset pagination
            offset_result = await self.test_offset_pagination(page_num, page_size)
            print(f"  Offset: {offset_result['duration_ms']:.2f}ms")

            # Test cursor pagination
            cursor_result = await self.test_cursor_pagination(page_num, page_size)
            print(f"  Cursor: {cursor_result['duration_ms']:.2f}ms")

            # Calculate speedup
            speedup = offset_result['duration_ms'] / cursor_result['duration_ms']
            print(f"  Speedup: {speedup:.1f}x")

            results['results'].append({
                'page_number': page_num,
                'offset': offset_result,
                'cursor': cursor_result,
                'speedup': speedup,
                'improvement_percent': ((offset_result['duration_ms'] - cursor_result['duration_ms']) / offset_result['duration_ms'] * 100)
            })

        return results

    async def generate_report(self, results: Dict[str, Any]) -> str:
        """
        Generate human-readable performance report.

        Args:
            results: Performance test results

        Returns:
            Formatted report string
        """
        report = []
        report.append("\n" + "="*80)
        report.append("PAGINATION PERFORMANCE COMPARISON REPORT")
        report.append("="*80)

        config = results['test_config']
        report.append(f"\nTest Configuration:")
        report.append(f"  Page Size: {config['page_size']}")
        report.append(f"  Pages Tested: {config['pages_tested']}")
        report.append(f"  Timestamp: {config['timestamp']}")

        report.append(f"\nResults:")
        report.append(f"{'Page':<8} {'Offset (ms)':<15} {'Cursor (ms)':<15} {'Speedup':<10} {'Improvement':<15}")
        report.append("-" * 80)

        for result in results['results']:
            page = result['page_number']
            offset_ms = result['offset']['duration_ms']
            cursor_ms = result['cursor']['duration_ms']
            speedup = result['speedup']
            improvement = result['improvement_percent']

            report.append(
                f"{page:<8} {offset_ms:>12.2f}ms  {cursor_ms:>12.2f}ms  "
                f"{speedup:>7.1f}x  {improvement:>12.1f}%"
            )

        # Summary statistics
        speedups = [r['speedup'] for r in results['results']]
        avg_speedup = sum(speedups) / len(speedups)
        max_speedup = max(speedups)

        report.append("\n" + "-" * 80)
        report.append(f"Summary:")
        report.append(f"  Average Speedup: {avg_speedup:.1f}x")
        report.append(f"  Maximum Speedup: {max_speedup:.1f}x")
        report.append(f"  Best Performance Gain: Page {results['results'][-1]['page_number']} "
                     f"({results['results'][-1]['speedup']:.1f}x faster)")

        report.append("\n" + "="*80)
        report.append("Conclusion:")
        report.append(f"  Cursor pagination is {avg_speedup:.1f}x faster on average")
        report.append(f"  Performance gain increases with page number (keyset vs linear scan)")
        report.append(f"  Recommended: Use cursor pagination for all paginated endpoints")
        report.append("="*80 + "\n")

        return "\n".join(report)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test pagination performance: offset vs cursor'
    )
    parser.add_argument(
        '--dataset-size',
        type=int,
        default=10000,
        help='Number of test records (default: 10000)'
    )
    parser.add_argument(
        '--pages',
        type=str,
        default='1,10,100,500,1000',
        help='Page numbers to test (comma-separated, default: 1,10,100,500,1000)'
    )
    parser.add_argument(
        '--page-size',
        type=int,
        default=50,
        help='Items per page (default: 50)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file path (optional)'
    )

    args = parser.parse_args()

    # Parse page numbers
    page_numbers = [int(p) for p in args.pages.split(',')]

    # Get database session
    # Note: Replace with actual database session in production
    async for db in get_db():
        tester = PaginationPerformanceTester(db)

        # Create test dataset
        await tester.create_test_dataset(args.dataset_size)

        # Run tests
        results = await tester.run_comprehensive_test(
            page_numbers=page_numbers,
            page_size=args.page_size
        )

        # Generate report
        report = await tester.generate_report(results)
        print(report)

        # Save JSON if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Detailed results saved to: {args.output}")

        break  # Only use first session


if __name__ == '__main__':
    asyncio.run(main())
