# API Spec

## Health

### `GET /api/health`

Returns service status and active providers.

## Documents

### `POST /api/documents/upload`

Multipart upload endpoint.

Response:

```json
{
  "document_id": "uuid",
  "filename": "lecture.pdf",
  "status": "indexed"
}
```

### `GET /api/documents`

Returns uploaded document summaries.

### `GET /api/documents/{document_id}`

Returns document metadata plus chunk count.

### `DELETE /api/documents/{document_id}`

Deletes the document, its stored file, and all indexed chunks.

### `POST /api/documents/{document_id}/reindex`

Rebuilds chunk and vector artifacts from the stored original file.

## Chat

### `POST /api/chat/ask`

Request body:

```json
{
  "question": "What does the report say about churn?",
  "mode": "auto",
  "selected_document_ids": [],
  "file_type": "pdf",
  "conversation_id": null
}
```

Response includes:

- `answer`
- `citations`
- `route_used`
- `conversation_id`
- `retrieved_chunks`
- `confidence_note`

## Conversations

### `GET /api/conversations`

Returns conversation summaries.

### `GET /api/conversations/{conversation_id}`

Returns message history and persisted citations.
