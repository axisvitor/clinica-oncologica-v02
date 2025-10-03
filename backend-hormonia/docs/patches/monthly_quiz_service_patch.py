"""
Patch for Backend/app/services/monthly_quiz_service.py

Multiple fixes for quiz submission flow:
1. Persist other_text in response_metadata
2. Update current_question_index after each response
3. Mark is_completed and completed_at when quiz finishes
4. Calculate and store total_score
5. Return new_token when rotation enabled
"""

# ============================================================================
# PATCH 1: Extract other_text from submit_data (around line 350)
# ============================================================================

# ADD AFTER LINE 349 (after question not found check):
"""
    # ✅ NEW: Extract other_text from metadata or direct field
    other_text = None
    if submit_data.response_metadata:
        other_text = submit_data.response_metadata.get("other_text")

    # Handle multiple choice response values (list support)
    response_value = submit_data.response_value
    question_type = question.get("type", "open_text")
    current_question_index = session.current_question_index  # ✅ Store for later use
"""


# ============================================================================
# PATCH 2: Store other_text in response_metadata (around line 404-415)
# ============================================================================

# REPLACE LINES 404-406:
# response_metadata = submit_data.response_metadata or {}
# response_metadata["is_encrypted"] = is_encrypted

# WITH:
"""
    # Create response metadata with all tracking info
    response_metadata = submit_data.response_metadata or {}
    response_metadata["is_encrypted"] = is_encrypted

    # ✅ NEW: Persist other_text in metadata
    if other_text:
        response_metadata["other_text"] = other_text

    # ✅ NEW: Store question index and submission time
    response_metadata["question_index"] = current_question_index
    response_metadata["submitted_at"] = datetime.utcnow().isoformat()
"""


# ============================================================================
# PATCH 3: Update session progress and calculate score (after line 418)
# ============================================================================

# ADD AFTER response creation (after line 418):
"""
    response = await self.quiz_response_service.create_response(response_create)

    # ✅ NEW: Update QuizSession progress
    total_questions = len(template.questions)
    session.current_question_index = current_question_index + 1

    # Check if quiz is complete
    if session.current_question_index >= total_questions:
        session.is_completed = True
        session.completed_at = datetime.utcnow()
        session.status = "completed"

        # ✅ NEW: Calculate total_score from all responses
        total_score = await self._calculate_total_score(session.id)
        session.total_score = total_score

    # Commit changes to session
    self.db.commit()
    self.db.refresh(session)
"""


# ============================================================================
# PATCH 4: Add token rotation and enhanced response (replace lines 440-444)
# ============================================================================

# REPLACE RETURN STATEMENT (lines 440-444):
# return {
#     "response_id": str(response.id),
#     "success": True,
#     "message": "Response submitted successfully"
# }

# WITH:
"""
    # Audit log response submission
    if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
        self.audit_service.log_response_submitted(
            patient_id=patient_id,
            session_id=session.id,
            question_id=submit_data.question_id,
            response_id=response.id,
            ip_address=ip_address,
            user_agent=user_agent
        )

    # ✅ NEW: Token rotation if enabled
    new_token = None
    if self.config.MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION:
        rotation_count = payload.get("rotation_count", 0) + 1

        # Generate new token with incremented rotation count
        expires_at = datetime.fromisoformat(payload["expires_at"])
        new_token = self._generate_token(
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            expires_at=expires_at,
            rotation_count=rotation_count
        )

        # Update token hash in session metadata
        metadata = session.session_metadata or {}
        metadata["token_hash"] = hashlib.sha256(new_token.encode()).hexdigest()
        metadata["rotation_count"] = rotation_count
        session.session_metadata = metadata
        self.db.commit()

        # Record token rotation metrics
        await self.metrics_collector.record_token_rotated(
            patient_id=str(patient_id),
            quiz_session_id=str(session.id),
            old_token_prefix=submit_data.token[:10],
            new_token_prefix=new_token[:10],
            rotation_count=rotation_count
        )

    # ✅ NEW: Return response with all required fields
    return {
        "response_id": str(response.id),
        "success": True,
        "message": "Response submitted successfully",
        "next_question_index": session.current_question_index,
        "is_completed": session.is_completed,
        "total_score": session.total_score if session.is_completed else None,
        "new_token": new_token  # ✅ Return rotated token for frontend
    }
"""


# ============================================================================
# PATCH 5: Add helper method for score calculation (add to class)
# ============================================================================

# ADD NEW METHOD TO MonthlyQuizService CLASS:
"""
    async def _calculate_total_score(self, session_id: UUID) -> int:
        \"\"\"
        Calculate total score from all responses in a quiz session.

        Args:
            session_id: Quiz session ID

        Returns:
            Total score as integer
        \"\"\"
        # Get all responses for this session
        responses = self.db.query(QuizResponse).filter(
            QuizResponse.quiz_session_id == session_id
        ).all()

        total_score = 0

        for response in responses:
            # Extract score from response_metadata if present
            metadata = response.response_metadata or {}
            score = metadata.get("score", 0)

            # If no score in metadata, apply default scoring logic
            if score == 0 and response.response_type == "scale":
                # For scale questions, value is the score
                try:
                    score = int(response.response_value)
                except (ValueError, TypeError):
                    score = 0
            elif score == 0 and response.response_type == "boolean":
                # For yes/no, assign 1 for positive responses
                if response.response_value.lower() in ["yes", "sim", "true", "1"]:
                    score = 1

            total_score += score

        return total_score
"""
