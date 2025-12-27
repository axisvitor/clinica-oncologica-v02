# Product Guidelines

## # Prose Style and Tone
*   **Patient-Facing (Quiz Interface, WhatsApp):**
    *   **Empathetic & Warm:** Language should be gentle, reassuring, and supportive. Avoid jargon; use clear, accessible terms.
    *   **Encouraging:** Use positive reinforcement to motivate users to complete quizzes and report their status.
    *   **Clarity First:** Instructions must be unambiguous to prevent confusion, especially for users who may be feeling unwell.
*   **Clinician-Facing (Dashboard, Reports):**
    *   **Professional & Clinical:** Maintain a high standard of medical accuracy and objectivity.
    *   **Concise & Efficient:** Present information in a way that allows for rapid scanning and assimilation. Use bullet points and summaries effectively.
    *   **Data-Driven:** Focus on clear presentation of metrics, trends, and actionable insights.

## # Design Principles
*   **Accessibility (Patient Focus):** The Quiz Interface must be fully accessible (WCAG 2.1 AA+ standards), considering users with varying levels of digital literacy and potential physical limitations due to treatment. Large touch targets, clear typography, and high contrast are key.
*   **Information Hierarchy (Clinician Focus):** The Dashboard should prioritize critical alerts and high-risk patient data. Use visual cues (color coding for risk levels) to guide attention immediately to where it's needed most.
*   **Responsiveness:**
    *   **Quiz:** Mobile-first design is critical as patients will likely access it via smartphones.
    *   **Dashboard:** Desktop-optimized for detailed analysis but must remain functional on tablets for rounds.

## # Brand & Visual Identity
*   **Color Palette:** Use calming, professional colors (e.g., soft blues, greens, neutrals) to evoke trust and stability. Avoid overly alarmist colors (like intense red) for patient-facing alerts; use softer indicators instead.
*   **Typography:** Use clean, sans-serif fonts that are highly legible on all screen sizes (e.g., Inter, Roboto).
*   **Consistency:** Maintain consistent UI components (buttons, cards, inputs) across the Frontend and Quiz Interface to reinforce a unified system feel.

## # User Experience (UX) Goals
*   **Minimize Friction:** The patient quiz completion process should be seamless and quick (< 5 minutes). Login/access should be as simple as possible (e.g., magic links).
*   **Actionable Insights:** For clinicians, every screen should offer a clear "next step" or action based on the data presented (e.g., "Review Alert," "Contact Patient").
