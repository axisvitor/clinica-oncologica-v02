"""
WebSocket endpoints for real-time communication.
"""
import json
import logging
import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.websocket_manager import connection_manager
from app.schemas.websocket import (
    AuthenticationRequest,
    AuthenticationResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    ErrorResponse,
    WebSocketEventType,
    create_websocket_message
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token")
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
        # Accept WebSocket connection first (before any authentication checks)
        logger.info(f"Accepting WebSocket connection: {connection_id}")
        await websocket.accept()

        # Store the connection in manager
        connection_manager.active_connections[connection_id] = websocket
        connection_manager.connection_metadata[connection_id] = {
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow(),
            "user_id": None,
            "patient_id": None,
            "authenticated": False
        }
        logger.info(f"WebSocket connection accepted: {connection_id}")
        
        # Send connection confirmation
        logger.info(f"Creating welcome message for: {connection_id}")
        welcome_message = create_websocket_message(
            WebSocketEventType.CONNECTED,
            {
                "connection_id": connection_id,
                "message": "WebSocket connection established",
                "authenticated": False
            }
        )
        logger.info(f"Welcome message created: {welcome_message.dict()}")
        
        logger.info(f"Sending welcome message to: {connection_id}")
        result = await connection_manager.send_personal_message(
            welcome_message.dict(), connection_id
        )
        logger.info(f"Welcome message sent result: {result} for {connection_id}")
        
        # Attempt authentication if token provided in query
        authenticated_user = None
        if token:
            # Get database session
            from app.database import get_db
            db_gen = get_db()
            db = next(db_gen)

            try:
                authenticated_user = await connection_manager.authenticate_connection(
                    connection_id, token, db
                )
            finally:
                # [P1 FIX] Close both session and generator to prevent connection leaks
                db.close()
                db_gen.close()
            
            auth_response = AuthenticationResponse(
                success=authenticated_user is not None,
                user_id=authenticated_user.id if authenticated_user else None,
                user_role=authenticated_user.role.value if authenticated_user and hasattr(authenticated_user.role, 'value') else str(authenticated_user.role) if authenticated_user else None,
                message="Authentication successful" if authenticated_user else "Authentication failed"
            )
            
            auth_message = create_websocket_message(
                WebSocketEventType.AUTHENTICATED,
                auth_response.dict()
            )
            await connection_manager.send_personal_message(
                auth_message.dict(), connection_id
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
                    await _handle_authentication(
                        connection_id, payload, websocket
                    )
                    
                elif message_type == "join_room":
                    await _handle_join_room(
                        connection_id, payload
                    )
                    
                elif message_type == "leave_room":
                    await _handle_leave_room(
                        connection_id, payload
                    )
                    
                elif message_type == "ping":
                    await _handle_ping(connection_id)
                    
                elif message_type == "pong":
                    await _handle_pong(connection_id)
                    
                else:
                    # Unknown message type
                    error_response = ErrorResponse(
                        error="unknown_message_type",
                        message=f"Unknown message type: {message_type}",
                        details={"received_type": message_type}
                    )
                    
                    error_message = create_websocket_message(
                        WebSocketEventType.ERROR,
                        error_response.dict()
                    )
                    await connection_manager.send_personal_message(
                        error_message.dict(), connection_id
                    )
                    
            except WebSocketDisconnect:
                # Client disconnected, break the loop
                logger.info(f"WebSocket client disconnected during message loop: {connection_id}")
                break
                
            except json.JSONDecodeError:
                # Invalid JSON received
                error_response = ErrorResponse(
                    error="invalid_json",
                    message="Invalid JSON format in message"
                )
                
                error_message = create_websocket_message(
                    WebSocketEventType.ERROR,
                    error_response.dict()
                )
                try:
                    await connection_manager.send_personal_message(
                        error_message.dict(), connection_id
                    )
                except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                    # Connection closed, break the loop
                    logger.debug(f"WebSocket connection error in JSON error handler: {e}")
                    break
                
            except Exception as e:
                error_str = str(e).lower()

                # Check if it's a connection-related error (WebSocket closed/disconnected)
                if any(keyword in error_str for keyword in [
                    "disconnect", "receive", "not connected", "websocket", "connection"
                ]):
                    logger.info(f"WebSocket connection error detected, breaking loop: {connection_id} - {e}")
                    break

                # For other errors, log and try to send error message
                logger.error(f"Error processing WebSocket message: {e}")

                error_response = ErrorResponse(
                    error="message_processing_error",
                    message="Error processing message"
                )

                error_message = create_websocket_message(
                    WebSocketEventType.ERROR,
                    error_response.dict()
                )
                try:
                    await connection_manager.send_personal_message(
                        error_message.dict(), connection_id
                    )
                except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                    # Connection closed, break the loop
                    logger.debug(f"WebSocket connection error in JSON error handler: {e}")
                    break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {connection_id}")
        
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        
    finally:
        # Clean up connection
        await connection_manager.disconnect(connection_id)
        
        # Send disconnection notification
        disconnect_message = create_websocket_message(
            WebSocketEventType.DISCONNECTED,
            {"connection_id": connection_id}
        )
        # Note: Can't send to disconnected client, but log for monitoring
        logger.info(f"WebSocket connection {connection_id} cleaned up")


async def _handle_authentication(
    connection_id: str,
    payload: dict,
    websocket: WebSocket
) -> None:
    """Handle authentication message."""
    try:
        auth_request = AuthenticationRequest(**payload)
        
        # Get database session
        from app.database import get_db
        db_gen = get_db()
        db = next(db_gen)

        try:
            authenticated_user = await connection_manager.authenticate_connection(
                connection_id, auth_request.token, db
            )
        finally:
            # [P1 FIX] Close both session and generator to prevent connection leaks
            db.close()
            db_gen.close()
        
        auth_response = AuthenticationResponse(
            success=authenticated_user is not None,
            user_id=authenticated_user.id if authenticated_user else None,
            user_role=authenticated_user.role.value if authenticated_user and hasattr(authenticated_user.role, 'value') else str(authenticated_user.role) if authenticated_user else None,
            message="Authentication successful" if authenticated_user else "Authentication failed"
        )
        
        auth_message = create_websocket_message(
            WebSocketEventType.AUTHENTICATED,
            auth_response.dict()
        )
        await connection_manager.send_personal_message(
            auth_message.dict(), connection_id
        )
        
    except Exception as e:
        logger.error(f"Authentication error for connection {connection_id}: {e}")
        error_response = ErrorResponse(
            error="authentication_error",
            message="Authentication failed"
        )
        
        error_message = create_websocket_message(
            WebSocketEventType.ERROR,
            error_response.dict()
        )
        await connection_manager.send_personal_message(
            error_message.dict(), connection_id
        )


async def _handle_join_room(
    connection_id: str,
    payload: dict
) -> None:
    """Handle join room message."""
    try:
        join_request = JoinRoomRequest(**payload)
        
        success = await connection_manager.join_patient_room(
            connection_id, str(join_request.patient_id)
        )
        
        join_response = JoinRoomResponse(
            success=success,
            patient_id=join_request.patient_id if success else None,
            message=f"Joined patient room {join_request.patient_id}" if success else "Failed to join room - authentication required"
        )
        
        response_message = create_websocket_message(
            WebSocketEventType.PATIENT_UPDATED,  # Using existing event type
            join_response.dict()
        )
        await connection_manager.send_personal_message(
            response_message.dict(), connection_id
        )
        
    except Exception as e:
        logger.error(f"Join room error for connection {connection_id}: {e}")
        error_response = ErrorResponse(
            error="join_room_error",
            message="Failed to join room"
        )
        
        error_message = create_websocket_message(
            WebSocketEventType.ERROR,
            error_response.dict()
        )
        await connection_manager.send_personal_message(
            error_message.dict(), connection_id
        )


async def _handle_leave_room(
    connection_id: str,
    payload: dict
) -> None:
    """Handle leave room message."""
    try:
        patient_id = payload.get("patient_id")
        if not patient_id:
            raise ValueError("patient_id is required")
        
        await connection_manager.leave_patient_room(connection_id, str(patient_id))
        
        response_data = {
            "success": True,
            "patient_id": patient_id,
            "message": f"Left patient room {patient_id}"
        }
        
        response_message = create_websocket_message(
            WebSocketEventType.PATIENT_UPDATED,  # Using existing event type
            response_data
        )
        await connection_manager.send_personal_message(
            response_message.dict(), connection_id
        )
        
    except Exception as e:
        logger.error(f"Leave room error for connection {connection_id}: {e}")
        error_response = ErrorResponse(
            error="leave_room_error",
            message="Failed to leave room"
        )
        
        error_message = create_websocket_message(
            WebSocketEventType.ERROR,
            error_response.dict()
        )
        await connection_manager.send_personal_message(
            error_message.dict(), connection_id
        )


async def _handle_ping(connection_id: str) -> None:
    """Handle ping message."""
    pong_message = create_websocket_message(
        WebSocketEventType.PONG,
        {"message": "pong"}
    )
    await connection_manager.send_personal_message(
        pong_message.dict(), connection_id
    )


async def _handle_pong(connection_id: str) -> None:
    """Handle pong message (response to server ping)."""
    # Update last ping time in connection metadata
    connection_info = connection_manager.get_connection_info(connection_id)
    if connection_info:
        connection_info["last_ping"] = connection_manager.connection_metadata[connection_id]["last_ping"]
    
    logger.debug(f"Received pong from connection {connection_id}")


@router.websocket("/patient/{patient_id}")
async def patient_websocket(
    websocket: WebSocket,
    patient_id: str,
    token: Optional[str] = Query(None, description="JWT authentication token")
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
        connection_manager.active_connections[connection_id] = websocket
        connection_manager.connection_metadata[connection_id] = {
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow(),
            "user_id": None,
            "patient_id": None,
            "authenticated": False
        }

        # Authenticate if token provided
        authenticated_user = None
        if token:
            # Get database session
            from app.database import get_db
            db_gen = get_db()
            db = next(db_gen)

            try:
                authenticated_user = await connection_manager.authenticate_connection(
                    connection_id, token, db
                )
            finally:
                # [P1 FIX] Close both session and generator to prevent connection leaks
                db.close()
                db_gen.close()

        if not authenticated_user:
            # Send authentication required message instead of closing immediately
            auth_error = ErrorResponse(
                error="authentication_required",
                message="Authentication required for patient monitoring. Please provide a valid JWT token via 'token' query parameter."
            )

            error_message = create_websocket_message(
                WebSocketEventType.ERROR,
                auth_error.dict()
            )
            await connection_manager.send_personal_message(
                error_message.dict(), connection_id
            )

            # Give client a moment to see the error message before closing
            import asyncio
            await asyncio.sleep(1)
            await websocket.close(code=4001, reason="Authentication required")
            return
        
        # Join patient room
        success = await connection_manager.join_patient_room(connection_id, patient_id)
        
        if not success:
            # Send room join error
            join_error = ErrorResponse(
                error="room_join_failed",
                message="Failed to join patient room"
            )
            
            error_message = create_websocket_message(
                WebSocketEventType.ERROR,
                join_error.dict()
            )
            await connection_manager.send_personal_message(
                error_message.dict(), connection_id
            )
            return
        
        # Send confirmation
        welcome_message = create_websocket_message(
            WebSocketEventType.CONNECTED,
            {
                "connection_id": connection_id,
                "patient_id": patient_id,
                "message": f"Connected to patient {patient_id} monitoring",
                "authenticated": True
            }
        )
        await connection_manager.send_personal_message(
            welcome_message.dict(), connection_id
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
        await connection_manager.disconnect(connection_id)