---
name: reelo
description: Complete video content production cycle with a 10-role think tank — automatic video fetch, subtitle extraction, analysis, script, title, image prompt, and SEO caption
triggers: [reelo, video cycle, reel production]
category: content-creation
---

# Reelo — Video Content Production Cycle

## When to use

- When the user asks for "reelo" with a link, a video name, or a search request
- To produce professional content from YouTube or Instagram videos
- When you need a reel script, title, image prompt, and SEO-optimized caption

## How to run

### Step 1: Receive input
Detect input type:
- If it's a YouTube/Instagram link → download directly
- If it's a search request (e.g. "go search") → use `web_search` to find a suitable video
- If it's a video name → use `web_search` to find the link

### Step 2: Extract subtitles
Use `terminal` with:
```bash
yt-dlp --skip-download --write-subs --sub-lang en,fa --convert-subs srt "<link>"
```

If no subtitles exist, use `yt-dlp` with `--write-auto-subs`.

Read the SRT file and convert it to a timeline table.

### Step 3: 10-role think tank
Simulate the following 10 roles and get each one's opinion:

1. **Chief Content Officer** — final decision maker, overall coordination
2. **Content Manager** — planning and execution oversight
3. **Copywriter** — writing engaging, captivating copy
4. **Graphic Designer** — cover image and visual element ideas
5. **Content Strategist** — overall direction, goal-setting and positioning
6. **Video Editor** — structure, rhythm and cuts
7. **Video Content Producer** — execution suggestions and recording techniques
8. **Scriptwriter** — writing the final script with dialogue
9. **Instagram Algorithm Specialist** — optimization for reach and explore
10. **Data Analyst** — performance review, improvement suggestions

For each role, ask for:
- Analysis of the video's tone and emotion (formal/casual/humorous/motivational)
- Target audience identification (age, gender, interests, knowledge level)
- Suggested CTA for the video's end

### Step 4: Video analysis
Based on the subtitles, extract:
- Main topic of the video
- Key message
- Content strengths and weaknesses
- Current structure (how it starts, progresses, ends)
- Overall tone and style

### Step 5: Write the reel script
Using the think tank output, write a complete script with these sections:

**Hook** — first 5-10 seconds that grab attention
**Body** — main content with proper rhythm
**CTA** — call to action matched to the content
**Closing** — wrap-up that creates a good feeling or curiosity

The script should be written to maximize viral potential.

### Step 5b: Edit plan — `08_EDIT_PLAN.md` (mandatory)

Every project that builds a reel from an existing video must also produce `08_EDIT_PLAN.md`; **a Reelo run without this file is not considered Complete.**

For each shot (Cut), write these fields precisely:

- `Reel Time` — shot time in the final reel
- `Source IN` — start second in the source video
- `Source OUT` — end second in the source video
- `Duration`
- `Exact Quote` — exact dialogue present in the Source (verbatim from subtitles, no rewriting)
- `Visual` — the visual that should be taken from the Source
- `On-screen Text` — text over the image
- `Edit Instruction` — Cut / Zoom / B-roll / Subtitle / Transition type
- `Audio` — original audio, music, or mix
- `Claim Note` — if there's a number or claim, mark whether it's the speaker's quote or brand copy

**Quote rule (mandatory):**
- If the speaker's real voice is used, never attribute a new sentence to the speaker.
- Only sentences already present in the Source subtitles (verbatim or trimmable) may be used as "speaker voice".
- Rewriting/paraphrasing is only allowed as On-screen Text or Narration and is labelled `paraphrase`.
- Do not delete `04_script.md` paraphrases; fix them in `08_EDIT_PLAN.md` and note: `Original script paraphrase — replaced with exact source quote.`

**Timing rule (mandatory):**
- If the subtitle only has a coarse range (like `00:35–02:00`), do not guess per-second Source IN/OUT.
- Label each Cut: `Exact` (precise time available) / `Approximate` (based on segment boundary) / `Needs source` (source must be listened to for precise time).

### Step 6: Persian cover title
Suggest 5 titles with these characteristics:
- Catchy and click-worthy
- Contains the main keyword
- 40-60 characters
- Creates curiosity or urgency

Pick the best one.

### Step 7: Image generation prompt
Based on the chosen title, write a precise prompt for Midjourney/DALL-E using this structure:
```
[style]: [subject] with [details] in [space] with [color scheme] and [mood]

Example:
A professional cinematic cover image for a YouTube video titled "[title]", featuring [scene description], with [dominant colors], [lighting], [emotional mood], ultra realistic, 8k, highly detailed, --ar 16:9
```

### Step 8: SEO-optimized caption
Write a caption with these characteristics:
- First line: a hook to attract follows and comments
- No hashtags (use natural keywords only)
- SEO-optimized for the Instagram algorithm
- 150-300 words
- Includes a call to comment and follow (natural tone)
- 2-3 questions to increase engagement

### Step 9: Save
Detect the destination folder:
- If the video is from the user's own channel or on a personal topic → `personal/`
- If it's from the company channel or on a company topic → `company/`
- Otherwise, ask the user

Folder structure per video:
```
/path/to/output/[personal|company]/YYYY-MM-DD_topic/
├── 01_subtitles.csv
├── 02_timeline_table.md
├── 03_analysis.md
├── 04_script.md
├── 05_cover_title.txt
├── 06_image_prompt.txt
├── 07_caption.txt
└── 08_EDIT_PLAN.md (mandatory — edit plan)
```

## Important notes

1. **When the user says "go search"**, use `web_search` with an appropriate query and find the best viral video.

2. **If there are no subtitles**, use `yt-dlp --write-auto-subs` or ask the user whether English subtitles are sufficient.

3. **Deliver the image prompt in the output** so the user can take it to their image tool of choice.

4. **Always ask the user before saving** whether the path is right or needs changing.

5. **If the video is from Instagram**, `yt-dlp` works with Instagram links too (as far as possible).

6. **The cycle cannot be complete without `08_EDIT_PLAN.md`** — after the script, build the edit plan (step 5b) following the quote and timing rules; otherwise the output is not Complete.

## Common errors

- If `yt-dlp` isn't installed → install with `pip install yt-dlp`
- If no subtitles are found → ask the user whether they have manual subtitles
- If there isn't enough space → warn the user

## Invocation examples

User: "reelo — write a script for an Instagram teaching video from my own channel"
→ find the link, run the full cycle, save under `personal/`

User: "reelo https://youtube.com/watch?v=..."
→ run directly on the given link

User: "reelo — go search for a viral video about AI"
→ search, pick the best, run the full cycle