"""
Tests for Parallel Query Execution Performance.

This module tests the parallel execution capabilities for analytics queries
and measures performance improvements over sequential execution.
"""
import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from unittest.mock import Mock, patch
from typing import List, Dict, Any, Callable
import statistics
import threading


class TestParallelQueryExecution:
    """Test parallel query execution performance and correctness."""
    
    @pytest.fixture
    def mock_database_connections(self):
        """Create mock database connections for parallel testing."""
        def create_connection(connection_id: int):
            conn = Mock()
            conn.connection_id = connection_id
            
            # Simulate different query execution times based on query type
            def execute_query(query: str, params: Dict = None):
                result = Mock()
                
                # Simulate realistic query execution times
                if "COUNT(*)" in query:
                    time.sleep(0.1)  # Fast count query
                    result.fetchone.return_value = {"count": 100 + connection_id}
                elif "AVG(" in query:
                    time.sleep(0.15)  # Average calculation
                    result.fetchone.return_value = {"avg": 75.5 + connection_id}
                elif "SUM(" in query:
                    time.sleep(0.12)  # Sum calculation
                    result.fetchone.return_value = {"sum": 1000 + connection_id * 10}
                elif "GROUP BY" in query:
                    time.sleep(0.2)  # Grouping query
                    result.fetchall.return_value = [
                        {"group": f"group_{i}", "value": i * 10} 
                        for i in range(5)
                    ]
                elif "ORDER BY" in query:
                    time.sleep(0.18)  # Sorting query
                    result.fetchall.return_value = [
                        {"id": i, "value": f"sorted_value_{i}"} 
                        for i in range(10)
                    ]
                else:
                    time.sleep(0.05)  # Default fast query
                    result.fetchall.return_value = [{"id": i} for i in range(5)]
                
                return result
            
            conn.execute = execute_query
            return conn
        
        # Create pool of connections
        return [create_connection(i) for i in range(5)]
    
    def test_sequential_vs_parallel_analytics_queries(self, mock_database_connections):
        """Compare sequential vs parallel execution of analytics queries."""
        # Define analytics queries that would typically run together
        analytics_queries = [
            "SELECT COUNT(*) as total_patients FROM patients WHERE doctor_id = 123",
            "SELECT AVG(engagement_score) as avg_engagement FROM patient_analytics WHERE doctor_id = 123",
            "SELECT SUM(message_count) as total_messages FROM daily_stats WHERE doctor_id = 123",
            "SELECT status, COUNT(*) as count FROM treatments WHERE doctor_id = 123 GROUP BY status",
            "SELECT created_at, patient_count FROM daily_patient_counts WHERE doctor_id = 123 ORDER BY created_at DESC LIMIT 30"
        ]
        
        # Sequential execution
        sequential_start = time.time()
        sequential_results = []
        
        connection = mock_database_connections[0]
        for query in analytics_queries:
            result = connection.execute(query)
            if "COUNT(*)" in query or "AVG(" in query or "SUM(" in query:
                sequential_results.append(result.fetchone())
            else:
                sequential_results.append(result.fetchall())
        
        sequential_time = (time.time() - sequential_start) * 1000
        
        # Parallel execution using ThreadPoolExecutor
        parallel_start = time.time()
        parallel_results = []
        
        def execute_single_query(query_info):
            query, connection = query_info
            result = connection.execute(query)
            if "COUNT(*)" in query or "AVG(" in query or "SUM(" in query:
                return result.fetchone()
            else:
                return result.fetchall()
        
        with ThreadPoolExecutor(max_workers=len(analytics_queries)) as executor:
            # Assign each query to a different connection
            query_connections = [
                (query, mock_database_connections[i % len(mock_database_connections)])
                for i, query in enumerate(analytics_queries)
            ]
            
            # Submit all queries for parallel execution
            futures = [executor.submit(execute_single_query, qc) for qc in query_connections]
            
            # Collect results
            for future in as_completed(futures):
                parallel_results.append(future.result())
        
        parallel_time = (time.time() - parallel_start) * 1000
        
        # Calculate performance metrics
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        improvement_percent = ((sequential_time - parallel_time) / sequential_time) * 100
        
        # Assertions
        assert len(parallel_results) == len(sequential_results), "Should get same number of results"
        assert parallel_time < sequential_time, f"Parallel should be faster: {parallel_time:.1f}ms vs {sequential_time:.1f}ms"
        assert speedup >= 2.5, f"Expected at least 2.5x speedup, got {speedup:.1f}x"
        assert improvement_percent >= 60, f"Expected >60% improvement, got {improvement_percent:.1f}%"
        
        return {
            "sequential_time": sequential_time,
            "parallel_time": parallel_time,
            "speedup": speedup,
            "improvement_percent": improvement_percent,
            "query_count": len(analytics_queries)
        }
    
    def test_parallel_execution_with_connection_pooling(self, mock_database_connections):
        """Test parallel execution with proper connection pool management."""
        # Simulate a larger number of queries than available connections
        query_count = 15
        connection_pool_size = len(mock_database_connections)
        
        queries = [f"SELECT * FROM analytics_table_{i} WHERE condition = {i}" for i in range(query_count)]
        
        # Track connection usage
        connection_usage = {conn.connection_id: 0 for conn in mock_database_connections}
        connection_lock = threading.Lock()
        
        def execute_with_pool_tracking(query_index):
            connection = mock_database_connections[query_index % connection_pool_size]
            
            with connection_lock:
                connection_usage[connection.connection_id] += 1
            
            query = queries[query_index]
            result = connection.execute(query)
            
            return {
                "query_index": query_index,
                "connection_id": connection.connection_id,
                "result": result.fetchall()
            }
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=connection_pool_size) as executor:
            futures = [executor.submit(execute_with_pool_tracking, i) for i in range(query_count)]
            results = [future.result() for future in as_completed(futures)]
        
        execution_time = (time.time() - start_time) * 1000
        
        # Verify connection pool usage
        total_usage = sum(connection_usage.values())
        assert total_usage == query_count, f"Expected {query_count} total usages, got {total_usage}"
        
        # Verify balanced connection usage (should be roughly equal)
        usage_values = list(connection_usage.values())
        usage_std = statistics.stdev(usage_values) if len(usage_values) > 1 else 0
        expected_usage_per_conn = query_count / connection_pool_size
        
        assert usage_std <= expected_usage_per_conn * 0.5, "Connection usage should be balanced"
        
        # Verify performance
        expected_sequential_time = query_count * 50  # Assuming 50ms per query
        speedup = expected_sequential_time / execution_time if execution_time > 0 else 0
        
        assert speedup >= connection_pool_size * 0.7, f"Expected speedup close to pool size, got {speedup:.1f}x"
        
        return {
            "execution_time": execution_time,
            "connection_usage": connection_usage,
            "speedup": speedup,
            "query_count": query_count,
            "pool_size": connection_pool_size
        }
    
    def test_parallel_execution_error_handling(self, mock_database_connections):
        """Test error handling in parallel query execution."""
        # Create queries where some will fail
        queries = [
            "SELECT COUNT(*) FROM patients",  # Success
            "SELECT * FROM non_existent_table",  # Will fail
            "SELECT AVG(score) FROM analytics",  # Success
            "INVALID SQL QUERY",  # Will fail
            "SELECT SUM(amount) FROM transactions"  # Success
        ]
        
        # Mock some connections to raise exceptions
        def failing_execute(query):
            if "non_existent_table" in query or "INVALID" in query:
                raise Exception(f"Database error for query: {query}")
            
            # Normal execution for valid queries
            result = Mock()
            result.fetchone.return_value = {"result": "success"}
            return result
        
        # Set up connections with error simulation
        for conn in mock_database_connections:
            conn.execute = failing_execute
        
        successful_results = []
        failed_queries = []
        
        def execute_with_error_handling(query_info):
            query, connection = query_info
            try:
                result = connection.execute(query)
                return {"success": True, "query": query, "result": result.fetchone()}
            except Exception as e:
                return {"success": False, "query": query, "error": str(e)}
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            query_connections = [
                (query, mock_database_connections[i % len(mock_database_connections)])
                for i, query in enumerate(queries)
            ]
            
            futures = [executor.submit(execute_with_error_handling, qc) for qc in query_connections]
            
            for future in as_completed(futures):
                result = future.result()
                if result["success"]:
                    successful_results.append(result)
                else:
                    failed_queries.append(result)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Verify error handling
        assert len(successful_results) == 3, f"Expected 3 successful queries, got {len(successful_results)}"
        assert len(failed_queries) == 2, f"Expected 2 failed queries, got {len(failed_queries)}"
        
        # Verify that failures didn't prevent other queries from completing
        successful_query_texts = [r["query"] for r in successful_results]
        assert "SELECT COUNT(*) FROM patients" in successful_query_texts
        assert "SELECT AVG(score) FROM analytics" in successful_query_texts
        assert "SELECT SUM(amount) FROM transactions" in successful_query_texts
        
        # Verify execution completed in reasonable time despite errors
        assert execution_time < 1000, f"Execution took too long: {execution_time:.1f}ms"
        
        return {
            "execution_time": execution_time,
            "successful_count": len(successful_results),
            "failed_count": len(failed_queries),
            "total_queries": len(queries)
        }
    
    def test_parallel_execution_with_different_query_complexities(self, mock_database_connections):
        """Test parallel execution with queries of varying complexity."""
        # Define queries with different complexity levels
        query_complexities = [
            {"query": "SELECT COUNT(*) FROM simple_table", "complexity": "simple", "expected_time": 0.05},
            {"query": "SELECT AVG(value) FROM medium_table WHERE condition = 1", "complexity": "medium", "expected_time": 0.15},
            {"query": "SELECT a.*, b.* FROM complex_table a JOIN other_table b ON a.id = b.ref_id GROUP BY a.category ORDER BY COUNT(*) DESC", "complexity": "complex", "expected_time": 0.25},
            {"query": "SELECT * FROM simple_lookup WHERE id = 123", "complexity": "simple", "expected_time": 0.05},
            {"query": "SELECT SUM(amount), AVG(score) FROM analytics_table WHERE date_range BETWEEN '2023-01-01' AND '2023-12-31'", "complexity": "medium", "expected_time": 0.15}
        ]
        
        # Mock connections to simulate different execution times
        def complexity_aware_execute(query):
            result = Mock()
            
            for qc in query_complexities:
                if qc["query"] == query:
                    time.sleep(qc["expected_time"])
                    break
            else:
                time.sleep(0.1)  # Default time
            
            result.fetchall.return_value = [{"result": f"data_for_{query[:20]}"}]
            return result
        
        for conn in mock_database_connections:
            conn.execute = complexity_aware_execute
        
        queries = [qc["query"] for qc in query_complexities]
        
        # Sequential execution
        sequential_start = time.time()
        for query in queries:
            mock_database_connections[0].execute(query)
        sequential_time = (time.time() - sequential_start) * 1000
        
        # Parallel execution
        parallel_start = time.time()
        
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            query_connections = [
                (query, mock_database_connections[i % len(mock_database_connections)])
                for i, query in enumerate(queries)
            ]
            
            futures = [
                executor.submit(lambda qc: qc[1].execute(qc[0]), qc)
                for qc in query_connections
            ]
            
            # Wait for all to complete
            for future in as_completed(futures):
                future.result()
        
        parallel_time = (time.time() - parallel_start) * 1000
        
        # Calculate expected times
        expected_sequential_time = sum(qc["expected_time"] for qc in query_complexities) * 1000
        expected_parallel_time = max(qc["expected_time"] for qc in query_complexities) * 1000
        
        # Verify performance matches expectations
        assert abs(sequential_time - expected_sequential_time) < 100, \
            f"Sequential time deviation too high: {sequential_time:.1f}ms vs expected {expected_sequential_time:.1f}ms"
        
        assert abs(parallel_time - expected_parallel_time) < 100, \
            f"Parallel time deviation too high: {parallel_time:.1f}ms vs expected {expected_parallel_time:.1f}ms"
        
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        
        # Should get significant speedup due to parallelization
        assert speedup >= 2.0, f"Expected at least 2x speedup, got {speedup:.1f}x"
        
        return {
            "sequential_time": sequential_time,
            "parallel_time": parallel_time,
            "expected_sequential_time": expected_sequential_time,
            "expected_parallel_time": expected_parallel_time,
            "speedup": speedup,
            "query_complexities": query_complexities
        }
    
    def test_parallel_execution_resource_limits(self, mock_database_connections):
        """Test parallel execution behavior under resource constraints."""
        # Test with limited thread pool sizes
        query_count = 20
        queries = [f"SELECT * FROM table_{i}" for i in range(query_count)]
        
        thread_pool_sizes = [1, 2, 4, 8, 16]
        results = {}
        
        for pool_size in thread_pool_sizes:
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=pool_size) as executor:
                futures = [
                    executor.submit(
                        mock_database_connections[i % len(mock_database_connections)].execute,
                        query
                    )
                    for i, query in enumerate(queries)
                ]
                
                # Wait for completion
                completed_count = 0
                for future in as_completed(futures):
                    future.result()
                    completed_count += 1
            
            execution_time = (time.time() - start_time) * 1000
            
            results[pool_size] = {
                "execution_time": execution_time,
                "throughput": (query_count / execution_time) * 1000 if execution_time > 0 else 0,
                "completed_queries": completed_count
            }
        
        # Verify all queries completed regardless of pool size
        for pool_size, result in results.items():
            assert result["completed_queries"] == query_count, \
                f"Pool size {pool_size}: Expected {query_count} completed queries, got {result['completed_queries']}"
        
        # Verify performance scaling
        assert results[2]["execution_time"] < results[1]["execution_time"], \
            "2 threads should be faster than 1"
        
        assert results[4]["execution_time"] < results[2]["execution_time"], \
            "4 threads should be faster than 2"
        
        # Find optimal pool size (best throughput)
        optimal_pool_size = max(results.keys(), key=lambda k: results[k]["throughput"])
        
        return {
            "results_by_pool_size": results,
            "optimal_pool_size": optimal_pool_size,
            "optimal_throughput": results[optimal_pool_size]["throughput"],
            "query_count": query_count
        }


class TestAsyncQueryExecution:
    """Test asynchronous query execution patterns."""
    
    @pytest.fixture
    def mock_async_connections(self):
        """Create mock async database connections."""
        async def create_async_connection(connection_id: int):
            conn = Mock()
            conn.connection_id = connection_id
            
            async def async_execute(query: str):
                # Simulate async I/O delay
                await asyncio.sleep(0.1)
                
                result = Mock()
                result.fetchall.return_value = [{"id": i, "conn": connection_id} for i in range(5)]
                return result
            
            conn.execute = async_execute
            return conn
        
        return [create_async_connection(i) for i in range(3)]
    
    @pytest.mark.asyncio
    async def test_async_parallel_query_execution(self, mock_async_connections):
        """Test async parallel query execution."""
        # Create async connections
        connections = []
        for create_conn in mock_async_connections:
            conn = await create_conn
            connections.append(conn)
        
        queries = [
            "SELECT * FROM async_table_1",
            "SELECT * FROM async_table_2", 
            "SELECT * FROM async_table_3",
            "SELECT * FROM async_table_4",
            "SELECT * FROM async_table_5"
        ]
        
        # Sequential async execution
        sequential_start = time.time()
        sequential_results = []
        
        for query in queries:
            result = await connections[0].execute(query)
            sequential_results.append(result.fetchall())
        
        sequential_time = (time.time() - sequential_start) * 1000
        
        # Parallel async execution
        parallel_start = time.time()
        
        async def execute_query(query, connection):
            return await connection.execute(query)
        
        # Create tasks for parallel execution
        tasks = [
            execute_query(query, connections[i % len(connections)])
            for i, query in enumerate(queries)
        ]
        
        # Execute all tasks concurrently
        parallel_results = await asyncio.gather(*tasks)
        parallel_results = [result.fetchall() for result in parallel_results]
        
        parallel_time = (time.time() - parallel_start) * 1000
        
        # Verify results
        assert len(parallel_results) == len(sequential_results)
        
        # Verify performance improvement
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        assert speedup >= 3.0, f"Expected significant async speedup, got {speedup:.1f}x"
        
        return {
            "sequential_time": sequential_time,
            "parallel_time": parallel_time,
            "speedup": speedup,
            "query_count": len(queries)
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])