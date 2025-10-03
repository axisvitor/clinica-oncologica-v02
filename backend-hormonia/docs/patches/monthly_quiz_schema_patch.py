"""
Patch for Backend/app/schemas/monthly_quiz.py

Fix: Add average_score field to MonthlyQuizStats schema
Lines: 103-117
"""

# ORIGINAL SCHEMA (lines 103-117):
"""
class MonthlyQuizStats(BaseModel):
    total_links_created: int = Field(..., description="Total links created")
    active_links: int = Field(..., description="Currently active links")
    expired_links: int = Field(..., description="Expired links")
    completed_quizzes: int = Field(..., description="Completed quizzes")
    completion_rate: float = Field(..., description="Completion rate percentage")
    average_completion_time: Optional[float] = Field(
        None,
        description="Average completion time in minutes"
    )
    delivery_methods_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of delivery methods"
    )
"""

# ENHANCED SCHEMA (add average_score field):
"""
class MonthlyQuizStats(BaseModel):
    \"\"\"Schema for monthly quiz statistics.\"\"\"
    total_links_created: int = Field(..., description="Total links created")
    active_links: int = Field(..., description="Currently active links")
    expired_links: int = Field(..., description="Expired links")
    completed_quizzes: int = Field(..., description="Completed quizzes")
    completion_rate: float = Field(..., description="Completion rate percentage")
    average_completion_time: Optional[float] = Field(
        None,
        description="Average completion time in minutes"
    )
    average_score: Optional[float] = Field(  # ✅ NEW FIELD
        None,
        description="Average score across completed quizzes"
    )
    delivery_methods_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of delivery methods"
    )
"""

# NOTE: The service method get_quiz_stats() already calculates average_score
# at line 1147 of monthly_quiz_service.py, so no service changes needed.
