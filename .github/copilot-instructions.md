# Copilot Instructions for voice_over_v3

Purpose
- Provide project-wide guidance for high-quality code suggestions aligned with repository architecture, workflows, and constraints.
- Reduce regressions by encoding non-negotiable requirements and preferred patterns.

Context & Goals
- App: Automate Vietnamese voice-over for videos from YouTube and DeepLearning.AI using LangGraph workflows.
- Priorities:
  - Preserve original YouTube description on upload (no translation, no truncation beyond API limits).
  - Reliable high-quality YouTube downloads despite SABR/403 via advanced yt-dlp strategies.
  - Keep legacy download path available for rollback; advanced path behind feature flag.
  - Use Google Gemini (2.5-flash) as default LLM with fallbacks to OpenAI/Groq.
  - Upload defaults: privacy unlisted; playlist from env.

Architecture (high level)
- src/voice_over/
  - nodes/: workflow nodes (download, audio, transcription, translation, tts, merge, upload, routing)
  - services/: YouTubeService, UploadService, TTS/Translation, etc.
  - models/: Pydantic models (WorkflowState, DownloadResult, etc.)
  - workflows/: LangGraph graphs and subgraphs
  - utils/: path/file/error helpers, ffmpeg helpers
- tests/: unit and integration tests
- code_demo/, docs/, debug scripts

Key Files
- src/voice_over/nodes/download_node.py: Dispatcher for legacy vs advanced downloader; batch and single flows.
- src/voice_over/services/youtube_service.py: Metadata extraction; legacy download; advanced downloader with clients/cookies/PO tokens/HLS/UA.
- tests/, tests/unit_tests/, tests/integration_tests/: testing suite.
- debug_ytdlp_link_test.py: Standalone troubleshooting tool for yt-dlp.
- SPECIFICATION.md, DEEPLEARNING_AI_SPECIFICATION.md: domain specs and architecture.

Non‑negotiable Functional Rules
- Do not translate or truncate the original YouTube description when uploading; keep as-is (respect YouTube API limits ~5,000 chars).
- Default upload privacy is unlisted; playlist ID read from environment.
- Maintain both download methods: do not remove legacy; advanced must be toggleable with env YT_ADVANCED_DOWNLOAD=1.
- Preserve and populate extended YouTube metadata in WorkflowState (channel_id, webpage_url, thumbnail, upload_date, view_count, like_count, categories, tags).

YouTube Downloading Guidelines
- Prefer advanced downloader when YT_ADVANCED_DOWNLOAD=1:
  - Player clients fallback order via env (PLAYER_CLIENTS): e.g., web, ios, web_safari, tv.
  - Cookies support (YT_COOKIES_FILE) with robust path resolution; only use where client supports cookies.
  - PO tokens (optional): PO_TOKEN_CLIENT, PO_TOKEN_GVS, PO_TOKEN_PLAYER, PO_TOKEN_SUBS.
  - Apple compatibility (APPLE_COMPAT=1) to ensure H.264/AAC MP4 outputs (QuickTime-friendly) with ffmpeg postprocessing (X264_CRF, X264_PRESET, AAC_BPS).
  - Format strategy: prefer HLS for iOS/web_safari; set iOS Safari UA; retry with HLS-first generic fallback, then bestv+besta fallback.
  - Respect desired vs available heights: use effective_height = min(DESIRED_HEIGHT, best_height_for_client). Enforce MIN_ACCEPT_HEIGHT; fallback to best available if enabled.
- Legacy downloader: keep as simple fallback; avoid changing defaults except quality selector and cookies file discovery.

Language & Coding Standards (Python)
- Python 3.11, PEP 8, type hints everywhere. Prefer pathlib over os.path where feasible.
- Use Pydantic models for state/config; avoid ad-hoc dicts for complex data.
- Logging via module loggers; avoid prints. Keep logs informative and concise. Emojis are acceptable in user-facing logs already in code; do not overuse.
- Error handling via ErrorHandler utilities; return structured DownloadResult/Processing results.
- Async boundaries: nodes may be async; heavy I/O dispatched via asyncio.to_thread when wrapping sync libraries (yt-dlp, ffmpeg).

Configuration & Environment
- Load .env using python-dotenv (find_dotenv when applicable). Do not assume cwd blindly; prefer robust loading.
- Key env vars:
  - Core: VIDEO_DIRECTORY, TRANSLATION_DOMAIN, LANGUAGE_CODE, VOICE_NAME, GENDER
  - LLMs: GOOGLE/GEMINI default with fallbacks to OPENAI/GROQ (keys via env)
  - Upload: YOUTUBE_PLAYLIST_ID, YOUTUBE_CATEGORY_ID, UPLOAD_PRIVACY_STATUS (default unlisted)
  - yt-dlp advanced: YT_ADVANCED_DOWNLOAD, DESIRED_HEIGHT, MIN_ACCEPT_HEIGHT, FALLBACK_TO_LOWEST, PLAYER_CLIENTS or PLAYER_CLIENT, YT_COOKIES_FILE
  - PO tokens: PO_TOKEN_CLIENT, PO_TOKEN_GVS, PO_TOKEN_PLAYER, PO_TOKEN_SUBS
  - Apple compat: APPLE_COMPAT, X264_CRF, X264_PRESET, AAC_BPS
- Never hardcode secrets or tokens. Do not log secret values. Mask sensitive paths when logging.

DeepLearning.AI Integration
- Prefer API-based scraping/parsing:
  - Course structure from __NEXT_DATA__ in HTML; avoid Selenium by default.
  - Video URLs via tRPC endpoint /api/trpc/course.getLessonVideo
  - Auth via exported cookies file (deeplearning_cookies.json) loaded explicitly.
- Video format: HLS (.m3u8). Ensure downloader supports HLS; reuse existing ffmpeg helpers.

Upload & Metadata
- Preserve original title and description. Translated metadata is separate; do not overwrite originals unless explicitly requested.
- Enforce YouTube API constraints (description length, categories). Use playlist from env if provided.

Testing & Quality
- Add/maintain unit tests in tests/unit_tests and integration tests in tests/integration_tests.
- Mock external APIs in unit tests (yt-dlp, Google TTS, LLMs, YouTube upload). Use real endpoints only in explicit integration tests guarded by env flags.
- Provide deterministic tests; avoid flakiness due to network. For yt-dlp, prefer probing/parsing functions in unit tests.

Preferred Patterns & Utilities
- Use PathManager for consistent paths across nodes. Use FileManager for disk space checks/FS ops. Use get_settings() for app settings.
- When adding fields to WorkflowState, update all readers/writers and ensure backward compatibility in downstream nodes.
- When changing function signatures, update all usages and tests.

Security & Compliance
- Do not commit secrets or cookies. Do not log tokens or cookies. Follow platform ToS.
- Validate file sizes and types post-download. Clean up temp files on failures when possible.

Performance
- Use retries for network I/O (yt-dlp already configured). Avoid unnecessary transcoding unless APPLE_COMPAT is requested.
- Consider concurrent processing where safe (audio segments). Keep memory footprint reasonable.

Pull Request Checklist for Copilot Suggestions
- Does the change respect non-negotiable rules (description preservation, upload defaults, legacy/advanced coexistence)?
- Are env vars documented and used safely? No secrets in logs?
- Are logging and error messages concise and actionable?
- Have all usages of edited functions/classes been updated? Add/adjust tests.
- Does the advanced downloader still handle clients/cookies/PO tokens/HLS correctly? No regression to 360p-only.

Examples (minimal, not exhaustive)
- Selecting advanced downloader in a node:
  - Read YT_ADVANCED_DOWNLOAD from env once at init; log current config.
  - When advanced is on, pass video_id/output_dir and optional desired_height; let service consume env for the rest.
- Adding a new env-controlled feature:
  - Define sane defaults; document in this file; log effective configuration on use; avoid breaking legacy.

What NOT to do
- Do not remove legacy code paths for downloading.
- Do not translate original YouTube description on upload.
- Do not hardcode quality, tokens, or paths; always allow env overrides.
- Do not introduce silent behavior changes without logs.

Contact for Ambiguities
- If a requirement conflicts with code, prefer the Non‑negotiable rules above and existing tests. Otherwise, add TODO with rationale and keep changes minimal.

