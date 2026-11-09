## TEST AGENT PROMPT – IMAGE INTEGRATION RULES ##
- Always use base64-encoded / real images for tests. Accepted formats: JPEG, PNG, WEBP only.
- Do not use SVG, BMP, HEIC. Do not upload blank, solid-color, or uniform-variance images.
- Every image must contain real visual features (objects, edges, text, textures).
- Re-detect MIME after any transformation. Extract first frame of animated images.
- Resize large images to reasonable bounds.
