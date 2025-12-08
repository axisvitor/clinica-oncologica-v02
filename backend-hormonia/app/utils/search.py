"""
Search utilities for GIN full-text search optimization.

This module provides helper functions to use PostgreSQL GIN indexes
for efficient text search operations.
"""

from typing import Optional, List
from sqlalchemy import func
from sqlalchemy.sql.expression import BinaryExpression, ColumnElement
from sqlalchemy.orm import InstrumentedAttribute


def gin_search(
    column: InstrumentedAttribute,
    search_term: str,
    language: str = 'simple'
) -> BinaryExpression:
    """
    Create a GIN full-text search expression.

    Uses PostgreSQL's to_tsvector and to_tsquery for efficient
    full-text search with GIN indexes.

    Args:
        column: SQLAlchemy column to search
        search_term: Search term (will be suffixed with :* for prefix matching)
        language: PostgreSQL text search language
                 - 'portuguese': For Brazilian Portuguese text (names, addresses)
                 - 'simple': For language-agnostic text (emails, IDs)

    Returns:
        SQLAlchemy binary expression for filtering

    Example:
        >>> from app.models.patient import Patient
        >>> from app.utils.search import gin_search
        >>>
        >>> # Search patient names (Portuguese)
        >>> patients = db.query(Patient).filter(
        ...     gin_search(Patient.name, 'maria', 'portuguese')
        ... ).all()
        >>>
        >>> # Search emails (simple)
        >>> users = db.query(User).filter(
        ...     gin_search(User.email, 'john@example', 'simple')
        ... ).all()
    """
    # Sanitize search term (prevent injection)
    sanitized_term = search_term.strip().replace("'", "''")

    # Add prefix wildcard for partial matching
    search_query = func.to_tsquery(language, f"{sanitized_term}:*")

    # Create full-text search expression
    return func.to_tsvector(language, column).op('@@')(search_query)


def gin_multi_term_search(
    column: InstrumentedAttribute,
    search_terms: List[str],
    operator: str = '&',
    language: str = 'simple'
) -> BinaryExpression:
    """
    Create a GIN search expression with multiple terms.

    Args:
        column: SQLAlchemy column to search
        search_terms: List of search terms
        operator: Boolean operator ('&' for AND, '|' for OR)
        language: PostgreSQL text search language

    Returns:
        SQLAlchemy binary expression for filtering

    Example:
        >>> # Search for "maria" AND "silva"
        >>> gin_multi_term_search(
        ...     Patient.name,
        ...     ['maria', 'silva'],
        ...     operator='&',
        ...     language='portuguese'
        ... )
        >>>
        >>> # Search for "maria" OR "ana"
        >>> gin_multi_term_search(
        ...     Patient.name,
        ...     ['maria', 'ana'],
        ...     operator='|',
        ...     language='portuguese'
        ... )
    """
    if not search_terms:
        raise ValueError("search_terms cannot be empty")

    if operator not in ('&', '|'):
        raise ValueError("operator must be '&' (AND) or '|' (OR)")

    # Sanitize and format search terms
    sanitized_terms = [term.strip().replace("'", "''") for term in search_terms]
    formatted_terms = [f"{term}:*" for term in sanitized_terms]

    # Join with operator
    query_string = f" {operator} ".join(formatted_terms)

    # Create search expression
    search_query = func.to_tsquery(language, query_string)
    return func.to_tsvector(language, column).op('@@')(search_query)


def hybrid_search(
    column: InstrumentedAttribute,
    search_term: str,
    language: str = 'simple',
    use_gin: bool = True
) -> BinaryExpression:
    """
    Hybrid search that can use either GIN or ILIKE.

    This provides a fallback mechanism for columns that may not
    have GIN indexes yet, or for development/testing purposes.

    Args:
        column: SQLAlchemy column to search
        search_term: Search term
        language: PostgreSQL text search language (used if use_gin=True)
        use_gin: Whether to use GIN index (True) or ILIKE fallback (False)

    Returns:
        SQLAlchemy binary expression for filtering

    Example:
        >>> # Use GIN index
        >>> hybrid_search(Patient.name, 'maria', 'portuguese', use_gin=True)
        >>>
        >>> # Fallback to ILIKE (for testing or columns without GIN)
        >>> hybrid_search(Patient.diagnosis, 'cancer', use_gin=False)
    """
    if use_gin:
        return gin_search(column, search_term, language)
    else:
        # Fallback to ILIKE for compatibility
        return column.ilike(f"%{search_term}%")


def create_search_rank(
    column: InstrumentedAttribute,
    search_term: str,
    language: str = 'simple'
) -> ColumnElement:
    """
    Create a search rank expression for result ordering.

    The rank indicates how well the text matches the search query.
    Higher ranks appear first when ordering by this expression.

    Args:
        column: SQLAlchemy column to rank
        search_term: Search term
        language: PostgreSQL text search language

    Returns:
        SQLAlchemy column expression for ranking

    Example:
        >>> from sqlalchemy import desc
        >>>
        >>> # Search and order by relevance
        >>> rank = create_search_rank(Patient.name, 'maria', 'portuguese')
        >>> patients = (
        ...     db.query(Patient, rank.label('rank'))
        ...     .filter(gin_search(Patient.name, 'maria', 'portuguese'))
        ...     .order_by(desc('rank'))
        ...     .all()
        ... )
    """
    # Sanitize search term
    sanitized_term = search_term.strip().replace("'", "''")
    search_query = func.to_tsquery(language, f"{sanitized_term}:*")

    # Create rank expression
    return func.ts_rank(
        func.to_tsvector(language, column),
        search_query
    )


def highlight_search_results(
    column: InstrumentedAttribute,
    search_term: str,
    language: str = 'simple',
    start_tag: str = '<mark>',
    stop_tag: str = '</mark>'
) -> ColumnElement:
    """
    Create an expression that highlights search matches in text.

    Useful for showing users which parts of the text matched their search.

    Args:
        column: SQLAlchemy column to highlight
        search_term: Search term
        language: PostgreSQL text search language
        start_tag: HTML/text tag to start highlighting
        stop_tag: HTML/text tag to end highlighting

    Returns:
        SQLAlchemy column expression with highlighted text

    Example:
        >>> # Get highlighted patient names
        >>> highlighted = highlight_search_results(
        ...     Patient.name,
        ...     'maria',
        ...     'portuguese',
        ...     start_tag='<strong>',
        ...     stop_tag='</strong>'
        ... )
        >>> patients = (
        ...     db.query(Patient, highlighted.label('highlighted_name'))
        ...     .filter(gin_search(Patient.name, 'maria', 'portuguese'))
        ...     .all()
        ... )
        >>> # Result: "highlighted_name" = "<strong>Maria</strong> Silva"
    """
    # Sanitize search term
    sanitized_term = search_term.strip().replace("'", "''")
    search_query = func.to_tsquery(language, f"{sanitized_term}:*")

    # Create highlight expression
    return func.ts_headline(
        language,
        column,
        search_query,
        f'StartSel={start_tag}, StopSel={stop_tag}'
    )


# Common language configurations for the application
class SearchLanguage:
    """Common language configurations for GIN search."""

    PORTUGUESE = 'portuguese'  # For Brazilian Portuguese text
    SIMPLE = 'simple'          # For language-agnostic text
    ENGLISH = 'english'        # For English text
    SPANISH = 'spanish'        # For Spanish text


# Example usage patterns
if __name__ == '__main__':
    """
    Example usage of search utilities.

    These examples show how to use the search utilities in your repositories.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Example 1: Simple GIN search
    logger.info("Example 1: Simple GIN search")
    logger.info("-" * 50)
    logger.info("""
    from app.models.patient import Patient
    from app.utils.search import gin_search, SearchLanguage

    # Search patient names
    patients = db.query(Patient).filter(
        gin_search(Patient.name, 'maria', SearchLanguage.PORTUGUESE)
    ).all()
    """)

    # Example 2: Multi-term search
    logger.info("\nExample 2: Multi-term search")
    logger.info("-" * 50)
    logger.info("""
    from app.utils.search import gin_multi_term_search, SearchLanguage

    # Search for "maria" AND "silva"
    patients = db.query(Patient).filter(
        gin_multi_term_search(
            Patient.name,
            ['maria', 'silva'],
            operator='&',
            language=SearchLanguage.PORTUGUESE
        )
    ).all()
    """)

    # Example 3: Search with ranking
    logger.info("\nExample 3: Search with ranking")
    logger.info("-" * 50)
    logger.info("""
    from app.utils.search import gin_search, create_search_rank, SearchLanguage
    from sqlalchemy import desc

    # Search and order by relevance
    rank = create_search_rank(Patient.name, 'maria', SearchLanguage.PORTUGUESE)
    patients = (
        db.query(Patient, rank.label('relevance'))
        .filter(gin_search(Patient.name, 'maria', SearchLanguage.PORTUGUESE))
        .order_by(desc('relevance'))
        .all()
    )
    """)

    # Example 4: Highlighted search results
    logger.info("\nExample 4: Highlighted search results")
    logger.info("-" * 50)
    logger.info("""
    from app.utils.search import gin_search, highlight_search_results, SearchLanguage

    # Get highlighted results
    highlighted = highlight_search_results(
        Patient.name,
        'maria',
        SearchLanguage.PORTUGUESE,
        start_tag='<mark>',
        stop_tag='</mark>'
    )

    patients = (
        db.query(Patient, highlighted.label('highlighted_name'))
        .filter(gin_search(Patient.name, 'maria', SearchLanguage.PORTUGUESE))
        .all()
    )

    for patient, highlighted_name in patients:
        logger.info(f"Original: {patient.name}")
        logger.info(f"Highlighted: {highlighted_name}")
    """)
