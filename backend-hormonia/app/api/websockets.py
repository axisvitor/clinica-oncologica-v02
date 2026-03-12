"""
WebSocket endpoints for real-time communication.
"""

import json
import logging
import uuid
from types import SimpleNamespace
from typing import Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query

from app.api.v2.auth_session_shared import (
    extract_canonical_user_from_session,
    get_user_data_from_session,
    resolve_session_id,
)
from app.config import settings
from app.services.websocket import get_websocket_manager
from app.schemas.websocket import (
    AuthenticationRequest,
    AuthenticationResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    ErrorResponse,
    WebSocketEventType,
    create_websocket_message,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)
router = APIRouter()

# Module-level WebSocket manager (lazy initialized)
_connection_manager_instance = None


def get_connection_manager():
    """Get or initialize the WebSocket connection manager singleton."""
    global _connection_manager_instance
    if _connection_manager_instance is None:
        _connection_manager_instance = get_websocket_manager()
    return _connection_manager_instance


AUTH_WEBSOCKET_SESSION_INVALID = "AUTH_WEBSOCKET_SESSION_INVALID"
AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED = "AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED"


def _mapping_get(mapping: Any, *keys: str) -> Optional[str]:
    if not mapping:
        return None

    for key in keys:
        try:
            value = mapping.get(key)
        except Exception:
            value = None
        if isinstance(value, str) and value:
            return value
    return None


async def _send_error_message(
    connection_id: str,
    *,
    error_code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    error_message = create_websocket_message(
        WebSocketEventType.ERROR,
        ErrorResponse(
            error=error_code,
            message=message,
            details=details,
        ).dict(),
    )
    await get_connection_manager().send_message(connection_id, error_message.dict())


async def _authenticate_websocket_via_session(
    websocket: WebSocket,
    *,
    connection_id: str,
    query_session_id: Optional[str],
) -> tuple[Optional[SimpleNamespace], bool]:
    """Authenticate a websocket from canonical session state.

    Returns a tuple of (authenticated_user, attempted_session_auth).
    When a session source is present but invalid, an explicit websocket error payload is
    emitted before returning (None, True).
    """
    headers = getattr(websocket, "headers", None)
    cookies = getattr(websocket, "cookies", None)

    final_session_id = resolve_session_id(
        authorization=_mapping_get(headers, "authorization", "Authorization"),
        x_session_id=_mapping_get(headers, "x-session-id", "X-Session-ID"),
        session_cookie_id=_mapping_get(
            cookies,
            settings.SESSION_COOKIE_NAME,
            "session_id",
        ),
        query_session_id=query_session_id,
    )

    if not final_session_id:
        return None, False

    details = {
        "connection_id": connection_id,
        "session_source": "query" if query_session_id else "cookie-or-header",
    }

    try:
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager

        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        redis_cache = FirebaseRedisCache(redis_client)

        session_data = await redis_cache.get_session(final_session_id)
        if not session_data:
            await _send_error_message(
                connection_id,
                error_code=AUTH_WEBSOCKET_SESSION_INVALID,
                message="Invalid or expired websocket session.",
                details=details,
            )
            logger.warning(
                "WebSocket session auth failed: missing session payload for connection %s",
                connection_id,
            )
            return None, True

        user_data = extract_canonical_user_from_session(session_data)

        db_gen = None
        db = None
        if not user_data:
            from app.database import get_db

            db_gen = get_db()
            db = next(db_gen)
            try:
                user_data = await get_user_data_from_session(
                    session_id=final_session_id,
                    db=db,
                    redis_cache=redis_cache,
                )
            finally:
                if db is not None:
                    db.close()
                if db_gen is not None:
                    db_gen.close()

        if not user_data or not user_data.get("is_active", False):
            await _send_error_message(
                connection_id,
                error_code=AUTH_WEBSOCKET_SESSION_INVALID,
                message="WebSocket session is not authorized.",
                details=details,
            )
            logger.warning(
                "WebSocket session auth rejected inactive/invalid user for connection %s",
                connection_id,
            )
            return None, True

        authenticated_user = SimpleNamespace(
            id=user_data.get("id") or session_data.get("user_id"),
            email=user_data.get("email"),
            role=user_data.get("role") or session_data.get("role") or "doctor",
            full_name=user_data.get("full_name"),
            is_active=bool(user_data.get("is_active", False)),
        )

        manager = get_connection_manager()
        if hasattr(manager, "_update_connection_metadata"):
            manager._update_connection_metadata(connection_id, authenticated_user)

        auth_message = create_websocket_message(
            WebSocketEventType.AUTHENTICATED,
            AuthenticationResponse(
                success=True,
                user_id=authenticated_user.id,
                user_role=str(authenticated_user.role),
                message="Session authentication successful",
            ).dict(),
        )
        await manager.send_message(connection_id, auth_message.dict())

        logger.info(
            "WebSocket authenticated via canonical session contract for connection %s",
            connection_id,
        )
        return authenticated_user, True
    except HTTPException as exc:
        logger.warning(
            "WebSocket session authentication rejected for connection %s: %s",
            connection_id,
            exc.detail,
        )
        await _send_error_message(
            connection_id,
            error_code=AUTH_WEBSOCKET_SESSION_INVALID,
            message=str(exc.detail),
            details=details,
        )
        return None, True
    except Exception as exc:
        logger.warning(
            "WebSocket session authentication lookup failed for connection %s: %s",
            connection_id,
            exc,
        )
        await _send_error_message(
            connection_id,
            error_code=AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED,
            message="Unable to verify websocket session right now.",
            details=details,
        )
        return None, True


@router.websocket("")
@router.websocket("/")
@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token"),
    session_id: Optional[str] = Query(
        None, description="Session ID for session-based auth"
    ),
) -> None:
    """
    Main WebSocket endpoint for real-time communication.

    Supports:
    - Authentication via JWT token (query param or message)
    - Patient room joining for targeted notifications
    - Real-time event broadcasting
    - Connection health monitoring

    Query Parameters:
        token: Optional JWT token for immediate authentication

    Message Types:
        - authenticate: Authenticate connection with JWT token
        - join_room: Join a patient room for notifications
        - leave_room: Leave a patient room
        - ping: Health check ping
        - pong: Response to server ping
    """
    connection_id = str(uuid.uuid4())

    try:
        # Connect using unified manager
        logger.info(f"Connecting WebSocket via unified manager: {connection_id}")
        connection_id = await get_connection_manager().connect(websocket, connection_id)
        logger.info(f"WebSocket connection accepted: {connection_id}")

        # Send connection confirmation before auth bootstrap so clients receive the
        # connection_id used by later authenticated/error diagnostics.
        logger.info(f"Creating welcome message for: {connection_id}")
        welcome_message = create_websocket_message(
            WebSocketEventType.CONNECTED,
            {
                "connection_id": connection_id,
                "message": "WebSocket connection established",
                "authenticated": False,
            },
        )
        logger.info(f"Welcome message created: {welcome_message.dict()}")

        logger.info(f"Sending welcome message to: {connection_id}")
        result = await get_connection_manager().send_message(
            connection_id, welcome_message.dict()
        )
        logger.info(f"Welcome message sent result: {result} for {connection_id}")

        # Attempt authentication if cookie/header/query session state or a legacy
        # token was supplied during the handshake.
        authenticated_user, attempted_session_auth = await _authenticate_websocket_via_session(
            websocket,
            connection_id=connection_id,
            query_session_id=session_id,
        )

        if attempted_session_auth and not authenticated_user:
            logger.info(
                "WebSocket closing after explicit session auth failure for connection %s",
                connection_id,
            )
            return

        # Fallback to token authentication only when no canonical session handshake
        # source was available.
        if not authenticated_user and token:
            # Get database session
            from app.database import get_db

            db_gen = get_db()
            db = next(db_gen)

            try:
                authenticated_user = (
                    await get_connection_manager().authenticate_connection(
                        connection_id, token, db
                    )
                )
            finally:
                # [P1 FIX] Close both session and generator to prevent connection leaks
                db.close()
                db_gen.close()

            auth_response = AuthenticationResponse(
                success=authenticated_user is not None,
                user_id=authenticated_user.id if authenticated_user else None,
                user_role=authenticated_user.role.value
                if authenticated_user and hasattr(authenticated_user.role, "value")
                else str(authenticated_user.role)
                if authenticated_user
                else None,
                message="Authentication successful"
                if authenticated_user
                else "Authentication failed",
            )

            auth_message = create_websocket_message(
                WebSocketEventType.AUTHENTICATED, auth_response.dict()
            )
            await get_connection_manager().send_message(
                connection_id, auth_message.dict()
            )

        # Message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)

                message_type = message_data.get("type")
                payload = message_data.get("data", {})

                # Handle different message types
                if message_type == "authenticate":
                    await _handle_authentication(connection_id, payload, websocket)

                elif message_type == "join_room":
                    await _handle_join_room(connection_id, payload)

                elif message_type == "leave_room":
                    await _handle_leave_room(connection_id, payload)

                elif message_type == "ping":
                    await _handle_ping(connection_id)

                elif message_type == "pong":
                    await _handle_pong(connection_id)

                else:
                    # Unknown message type
                    error_response = ErrorResponse(
                        error="unknown_message_type",
                        message=f"Unknown message type: {message_type}",
                        details={"received_type": message_type},
                    )

                    error_message = create_websocket_message(
                        WebSocketEventType.ERROR, error_response.dict()
                    )
                    await get_connection_manager().send_message(
                        connection_id, error_message.dict()
                    )

            except WebSocketDisconnect:
                # Client disconnected, break the loop
                logger.info(
                    f"WebSocket client disconnected during message loop: {connection_id}"
                )
                break

            except json.JSONDecodeError:
                # Invalid JSON received
                error_response = ErrorResponse(
                    error="invalid_json", message="Invalid JSON format in message"
                )

                error_message = create_websocket_message(
                    WebSocketEventType.ERROR, error_response.dict()
                )
                try:
                    await get_connection_manager().send_message(
                        connection_id, error_message.dict()
                    )
                except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                    # Connection closed, break the loop
                    logger.debug(
                        f"WebSocket connection error in JSON error handler: {e}"
                    )
                    break

            except Exception as e:
                error_str = str(e).lower()

                # Check if it's a connection-related error (WebSocket closed/disconnected)
                if any(
                    keyword in error_str
                    for keyword in [
                        "disconnect",
                        "receive",
                        "not connected",
                        "websocket",
                        "connection",
                    ]
                ):
                    logger.info(
                        f"WebSocket connection error detected, breaking loop: {connection_id} - {e}"
                    )
                    break

                # For other errors, log and try to send error message
                logger.error(f"Error processing WebSocket message: {e}")

                error_response = ErrorResponse(
                    error="message_processing_error", message="Error processing message"
                )

                error_message = create_websocket_message(
                    WebSocketEventType.ERROR, error_response.dict()
                )
                try:
                    await get_connection_manager().send_message(
                        connection_id, error_message.dict()
                    )
                except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                    # Connection closed, break the loop
                    logger.debug(
                        f"WebSocket connection error in JSON error handler: {e}"
                    )
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {connection_id}")

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")

    finally:
        # Clean up connection
        await get_connection_manager().disconnect(connection_id)

        # Send disconnection notification
        create_websocket_message(
            WebSocketEventType.DISCONNECTED, {"connection_id": connection_id}
        )
        # Note: Can't send to disconnected client, but log for monitoring
        logger.info(f"WebSocket connection {connection_id} cleaned up")


async def _handle_authentication(
    connection_id: str, payload: dict, websocket: WebSocket
) -> None:
    """Handle authentication message."""
    try:
        auth_request = AuthenticationRequest(**payload)

        # Get database session
        from app.database import get_db

        db_gen = get_db()
        db = next(db_gen)

        try:
            authenticated_user = await get_connection_manager().authenticate_connection(
                connection_id, auth_request.token, db
            )
        finally:
            # [P1 FIX] Close both session and generator to prevent connection leaks
            db.close()
            db_gen.close()

        auth_response = AuthenticationResponse(
            success=authenticated_user is not None,
            user_id=authenticated_user.id if authenticated_user else None,
            user_role=authenticated_user.role.value
            if authenticated_user and hasattr(authenticated_user.role, "value")
            else str(authenticated_user.role)
            if authenticated_user
            else None,
            message="Authentication successful"
            if authenticated_user
            else "Authentication failed",
        )

        auth_message = create_websocket_message(
            WebSocketEventType.AUTHENTICATED, auth_response.dict()
        )
        await get_connection_manager().send_message(connection_id, auth_message.dict())

    except Exception as e:
        logger.error(f"Authentication error for connection {connection_id}: {e}")
        error_response = ErrorResponse(
            error="authentication_error", message="Authentication failed"
        )

        error_message = create_websocket_message(
            WebSocketEventType.ERROR, error_response.dict()
        )
        await get_connection_manager().send_message(connection_id, error_message.dict())


async def _handle_join_room(connection_id: str, payload: dict) -> None:
    """Handle join room message."""
    try:
        join_request = JoinRoomRequest(**payload)

        success = await get_connection_manager().join_patient_room(
            connection_id, str(join_request.patient_id)
        )

        join_response = JoinRoomResponse(
            success=success,
            patient_id=join_request.patient_id if success else None,
            message=f"Joined patient room {join_request.patient_id}"
            if success
            else "Failed to join room - authentication required",
        )

        response_message = create_websocket_message(
            WebSocketEventType.PATIENT_UPDATED,  # Using existing event type
            join_response.dict(),
        )
        await get_connection_manager().send_message(
            connection_id, response_message.dict()
        )

    except Exception as e:
        logger.error(f"Join room error for connection {connection_id}: {e}")
        error_response = ErrorResponse(
            error="join_room_error", message="Failed to join room"
        )

        error_message = create_websocket_message(
            WebSocketEventType.ERROR, error_response.dict()
        )
        await get_connection_manager().send_message(connection_id, error_message.dict())


async def _handle_leave_room(connection_id: str, payload: dict) -> None:
    """Handle leave room message."""
    try:
        patient_id = payload.get("patient_id")
        if not patient_id:
            raise ValueError("patient_id is required")

        await get_connection_manager().leave_patient_room(
            connection_id, str(patient_id)
        )

        response_data = {
            "success": True,
            "patient_id": patient_id,
            "message": f"Left patient room {patient_id}",
        }

        response_message = create_websocket_message(
            WebSocketEventType.PATIENT_UPDATED,  # Using existing event type
            response_data,
        )
        await get_connection_manager().send_message(
            connection_id, response_message.dict()
        )

    except Exception as e:
        logger.error(f"Leave room error for connection {connection_id}: {e}")
        error_response = ErrorResponse(
            error="leave_room_error", message="Failed to leave room"
        )

        error_message = create_websocket_message(
            WebSocketEventType.ERROR, error_response.dict()
        )
        await get_connection_manager().send_message(connection_id, error_message.dict())


async def _handle_ping(connection_id: str) -> None:
    """Handle ping message."""
    pong_message = create_websocket_message(
        WebSocketEventType.PONG, {"message": "pong"}
    )
    await get_connection_manager().send_message(connection_id, pong_message.dict())


async def _handle_pong(connection_id: str) -> None:
    """Handle pong message (response to server ping)."""
    # Update last ping time in connection metadata
    connection_info = get_connection_manager().get_connection_info(connection_id)
    if connection_info:
        connection_info["last_ping"] = get_connection_manager().connection_metadata[
            connection_id
        ]["last_ping"]

    logger.debug(f"Received pong from connection {connection_id}")


@router.websocket("/patient/{patient_id}")
async def patient_websocket(
    websocket: WebSocket,
    patient_id: str,
    token: Optional[str] = Query(None, description="JWT authentication token"),
) -> None:
    """
    Dedicated WebSocket endpoint for patient-specific real-time updates.

    This endpoint automatically joins the patient room upon connection
    and is designed for healthcare providers monitoring specific patients.

    Path Parameters:
        patient_id: UUID of the patient to monitor

    Query Parameters:
        token: JWT authentication token
    """
    connection_id = str(uuid.uuid4())

    try:
        # Accept WebSocket connection first
        await websocket.accept()

        # Store the connection in manager
        get_connection_manager().active_connections[connection_id] = websocket
        get_connection_manager().connection_metadata[connection_id] = {
            "connected_at": now_sao_paulo(),
            "last_ping": now_sao_paulo(),
            "user_id": None,
            "patient_id": None,
            "authenticated": False,
        }

        # Authenticate if token provided
        authenticated_user = None
        if token:
            # Get database session
            from app.database import get_db

            db_gen = get_db()
            db = next(db_gen)

            try:
                authenticated_user = (
                    await get_connection_manager().authenticate_connection(
                        connection_id, token, db
                    )
                )
            finally:
                # [P1 FIX] Close both session and generator to prevent connection leaks
                db.close()
                db_gen.close()

        if not authenticated_user:
            # Send authentication required message instead of closing immediately
            auth_error = ErrorResponse(
                error="authentication_required",
                message="Authentication required for patient monitoring. Please provide a valid JWT token via 'token' query parameter.",
            )

            error_message = create_websocket_message(
                WebSocketEventType.ERROR, auth_error.dict()
            )
            await get_connection_manager().send_message(
                connection_id, error_message.dict()
            )

            # Give client a moment to see the error message before closing
            import asyncio

            await asyncio.sleep(1)
            await websocket.close(code=4001, reason="Authentication required")
            return

        # Join patient room
        success = await get_connection_manager().join_patient_room(
            connection_id, patient_id
        )

        if not success:
            # Send room join error
            join_error = ErrorResponse(
                error="room_join_failed", message="Failed to join patient room"
            )

            error_message = create_websocket_message(
                WebSocketEventType.ERROR, join_error.dict()
            )
            await get_connection_manager().send_message(
                connection_id, error_message.dict()
            )
            return

        # Send confirmation
        welcome_message = create_websocket_message(
            WebSocketEventType.CONNECTED,
            {
                "connection_id": connection_id,
                "patient_id": patient_id,
                "message": f"Connected to patient {patient_id} monitoring",
                "authenticated": True,
            },
        )
        await get_connection_manager().send_message(
            connection_id, welcome_message.dict()
        )

        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                # Handle ping/pong for connection health
                if message_data.get("type") == "ping":
                    await _handle_ping(connection_id)
                elif message_data.get("type") == "pong":
                    await _handle_pong(connection_id)

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from connection {connection_id}")
            except Exception as e:
                logger.error(f"Error processing patient WebSocket message: {e}")

    except WebSocketDisconnect:
        logger.info(f"Patient WebSocket client disconnected: {connection_id}")

    except Exception as e:
        logger.error(f"Patient WebSocket connection error: {e}")

    finally:
        # Clean up connection
        await get_connection_manager().disconnect(connection_id)
