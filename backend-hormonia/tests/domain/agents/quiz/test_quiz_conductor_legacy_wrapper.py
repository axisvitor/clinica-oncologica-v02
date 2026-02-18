from app.agents.communication import QuizConductor
from app.domain.agents.quiz import QuizConductor as DomainQuizConductor


def test_quiz_conductor_export_points_to_domain_class():
    assert QuizConductor is DomainQuizConductor
