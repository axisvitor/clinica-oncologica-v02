"""
Script to apply 3 critical fixes to sequential_message_handler.py
"""
import re

# Read file
filepath = 'app/services/flow/sequential_message_handler.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

original_content = content

# === FIX 1: Return skip instead of error for missing day config ===
old1 = 'return {"status": "error", "message": f"No config for day {day_number} in {flow_kind}"}'
new1 = '''# FIX: Return skip instead of error for days without config
                logger.info(f"No config for day {day_number} in {flow_kind} - skipping")
                return {"status": "skip", "message": f"No messages configured for day {day_number}"}'''

if old1 in content:
    content = content.replace(old1, new1)
    print('✅ Fix 1 applied: skip for missing day config')
else:
    print('❌ Fix 1: pattern not found')

# === FIX 2: Reset message index when day changes ===
old2 = '''# Get current state data
            step_data = flow_state.step_data or {}
            current_index = step_data.get("current_day_message_index", 0)'''

new2 = '''# Get current state data
            step_data = flow_state.step_data or {}
            
            # FIX 2: Reset message index when day changes to avoid skipping first message
            previous_day = step_data.get("current_flow_day")
            if previous_day is not None and previous_day != day_number:
                logger.debug(f"Day changed from {previous_day} to {day_number} - resetting message index")
                step_data["current_day_message_index"] = 0
                step_data["day_complete"] = False
                step_data["awaiting_response"] = False
            
            current_index = step_data.get("current_day_message_index", 0)'''

if old2 in content:
    content = content.replace(old2, new2)
    print('✅ Fix 2 applied: reset index on day change')
else:
    print('❌ Fix 2: pattern not found')

# === FIX 3: Auto-advance in wait_each mode ===
old3 = '''elif send_mode == "wait_each":
                # Send one message at a time
                return await self._send_message_and_wait(patient, messages, current_index, flow_state, day_number, flow_kind)'''

new3 = '''elif send_mode == "wait_each":
                # FIX 3: Auto-advance through messages that don't expect response
                return await self._send_wait_each_with_auto_advance(
                    patient, messages, current_index, flow_state, day_number, flow_kind
                )'''

if old3 in content:
    content = content.replace(old3, new3)
    print('✅ Fix 3 applied: wait_each auto-advance')
else:
    print('❌ Fix 3: pattern not found')

# Write file if changes were made
if content != original_content:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('\n✅ File saved successfully!')
else:
    print('\n⚠️ No changes made')
