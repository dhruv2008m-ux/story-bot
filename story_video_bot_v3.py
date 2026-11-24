"""
Free daily video maker for 3 YouTube channels.

  kids_en    : English kids' stories + rhymes (alternates by day), 3D-cartoon AI images
  kids_hi    : Hindi kids' stories + rhymes (alternates by day), 3D-cartoon AI images
  village_hi : Hindi village stories (shop, ghost, farmer...), hand-drawn-style 2D characters
               made in code (12 fixed faces, new names + dress every video)

Setup (once):
  pip install -r requirements.txt
  Install FFmpeg (https://ffmpeg.org)
  Free Gemini key: https://aistudio.google.com/apikey
  export GEMINI_API_KEY="your_key"      (Windows: set GEMINI_API_KEY=your_key)
Keep village_art.py in the same folder.

Run:  python story_video_bot_v3.py kids_en      (or kids_hi / village_hi / all)
Optional: TOPIC="your idea"  MODE=story|rhyme (kids channels)
Output: output/<date>/<channel>/video.mp4, short.mp4, thumbnail.jpg, info.txt
"""
import os, sys, json, time, asyncio, datetime, random, urllib.parse
import requests
import edge_tts
from moviepy.editor import (ImageClip, AudioFileClip, CompositeVideoClip, ColorClip,
                            concatenate_videoclips, concatenate_audioclips)
from moviepy.video.fx.all import crop
import village_art as art

MODEL = "gemini-2.5-flash"
KIDS_STYLE = ("cute colorful 3D cartoon style for children, soft bright lighting, "
              "friendly smiling characters, main subject centered, no text")

CHANNELS = {
    "kids_en": dict(lang="en", voice="en-US-AnaNeural", kind="kids"),
    "kids_hi": dict(lang="hi", voice="hi-IN-SwaraNeural", kind="kids"),
    "village_hi": dict(lang="hi", voice="hi-IN-MadhurNeural", kind="village"),
}
LANG_NAME = {"en": "simple English", "hi": "simple spoken Hindi in Devanagari script"}

# ---------------------------------------------------------------- random idea pools
KIDS_HEROES = ["a baby elephant", "a little bunny", "a tiny kitten", "a baby duck", "a puppy",
               "a baby monkey", "a lion cub", "a baby panda", "a small turtle", "a baby parrot",
               "a little fox", "a baby bear", "a baby giraffe", "a little girl", "a little boy"]
KIDS_THEMES = ["sharing", "honesty", "kindness", "good habits like brushing teeth", "helping friends",
               "bravery", "never giving up", "listening to parents", "cleanliness", "saying sorry and thank you",
               "patience", "teamwork", "not being greedy"]
KIDS_PLACES = ["jungle", "farm", "garden", "pond", "snowy hills", "beach", "magic forest", "school", "village"]
RHYME_THEMES = ["colors", "counting 1 to 10", "fruits", "vehicles", "rain", "animal sounds", "days of the week",
                "body parts", "morning routine", "birds", "bedtime", "vegetables"]
GENRES = ["a village roadside shop or street-food seller who struggles and then succeeds",
          "a mild ghost story in a village with a clever, logical or funny twist ending (spooky, no gore)",
          "an honest farmer versus a greedy moneylender",
          "a clever child who solves a village problem",
          "a village fair (mela) mystery",
          "a mysterious traveller who tests the villagers' kindness",
          "a poor craftsman whose skill finally earns respect",
          "a jealous neighbour whose plan backfires",
          "a missing-goat or missing-money mystery solved by a smart villager"]
JOBS = ["tea seller", "tailor", "potter", "farmer", "cobbler", "sweet maker", "milkman", "barber",
        "cycle repair man", "postman", "grocery shopkeeper", "vegetable seller", "school teacher", "fisherman"]
MALE_NAMES = ["रमेश", "सुरेश", "भोला", "गोपाल", "मोहन", "किशन", "बलराम", "हरि", "शंकर", "दीनू", "लल्लू", "बिरजू",
              "मंगल", "रामू", "श्यामू", "धर्मेंद्र", "जगन", "नंदू", "कालू", "भगत", "रघु", "महेश"]
FEMALE_NAMES = ["सुनीता", "गीता", "राधा", "कमला", "पार्वती", "मीना", "लक्ष्मी", "सरोज", "रेखा", "बिमला", "चंपा",
                "शांति", "पुष्पा", "सावित्री", "कजरी", "बसंती", "धनिया", "रुक्मणी", "फूलमती", "तारा"]
KID_NAMES = ["छोटू", "गुड़िया", "चुन्नू", "मुन्नी", "पप्पू", "गोलू", "बबली", "टिंकू", "मिंटू", "रानी", "सोनू", "पिंकी"]

SCHEMA_KIDS = ('Return JSON: {"title": "catchy title under 70 chars", "description": "...", '
               '"tags": ["..."], "character": "one-line fixed visual description of the main '
               'characters (English)", "scenes": [{"narration": "...", "image": '
               '"short visual description of the scene (English)"}]}')


# ---------------------------------------------------------------- helpers
def gemini(prompt):
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    r = None
    for _ in range(4):
        r = requests.post(url, json=body, timeout=180)
        if r.ok:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        time.sleep(20)
    r.raise_for_status()


def load_history(name):
    try:
        with open(f"history_{name}.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(name, title):
    h = (load_history(name) + [title])[-60:]
    with open(f"history_{name}.json", "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def avoid_text(hist):
    return ("Do NOT repeat or resemble these earlier stories: " + "; ".join(hist[-30:])) if hist else ""


async def _tts(text, voice, path, rate, pitch):
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path)


def tts(text, voice, path, rate="+0%", pitch="+0Hz"):
    for i in range(4):
        try:
            asyncio.run(_tts(text, voice, path, rate, pitch))
            return
        except Exception:
            time.sleep(3 * (i + 1))
    raise RuntimeError("TTS failed for: " + text[:40])


def make_image(prompt, path, seed):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
           f"?width=1280&height=720&nologo=true&seed={seed}")
    for i in range(6):
        try:
            r = requests.get(url, timeout=120)
            if r.ok and len(r.content) > 5000:
                with open(path, "wb") as f:
                    f.write(r.content)
                return
        except requests.RequestException:
            pass
        time.sleep(10 * (i + 1))
    raise RuntimeError("Image failed: " + prompt[:50])


def assemble(images, audio_lists, outdir, repeat=1, short_mode="crop"):
    """images: list of jpg paths; audio_lists: list (per scene) of lists of audio files."""
    clips = []
    for img, files in zip(images, audio_lists):
        audio = concatenate_audioclips([AudioFileClip(f) for f in files])
        d = audio.duration + 0.5
        zoom = (ImageClip(img).set_duration(d)
                .resize(lambda t, d=d: 1 + 0.06 * t / d).set_position("center"))
        clips.append(CompositeVideoClip([zoom], size=(1280, 720)).set_audio(audio))

    first = concatenate_videoclips(clips[:5])
    if short_mode == "crop":
        short = crop(first, width=406, height=720, x_center=640, y_center=360).resize((1080, 1920))
    else:  # letterbox: full 16:9 picture in the middle of a vertical frame
        bg = ColorClip((1080, 1920), color=(18, 18, 28)).set_duration(first.duration)
        fg = first.resize(width=1080).set_position("center")
        short = CompositeVideoClip([bg, fg], size=(1080, 1920)).set_audio(first.audio)
    short.write_videofile(os.path.join(outdir, "short.mp4"), fps=24, preset="veryfast",
                          threads=2, logger=None)
    full = concatenate_videoclips(clips * repeat)
    full.write_videofile(os.path.join(outdir, "video.mp4"), fps=24, preset="veryfast",
                         threads=2, logger=None)


def write_info(out, story, extra=""):
    with open(os.path.join(out, "info.txt"), "w", encoding="utf-8") as f:
        f.write(f"TITLE:\n{story['title']}\n\nDESCRIPTION:\n{story['description']}\n\n"
                f"TAGS:\n{', '.join(story.get('tags', []))}\n{extra}")


# ---------------------------------------------------------------- kids channels
def kids_prompt(cfg, mode, topic):
    lang = LANG_NAME[cfg["lang"]]
    if mode == "rhyme":
        return f"""Write an ORIGINAL nursery rhyme song for toddlers in {lang} (do NOT copy any existing rhyme).
{topic}
Rules: 4 verses of 4 short rhyming lines, plus a catchy 2-line chorus repeated after every verse. Simple words, strong rhythm.
Make exactly 10 scenes. Each narration is 2 lines of the lyrics. Each image is a cute child-friendly picture for those lines.
{SCHEMA_KIDS}"""
    return f"""Write an ORIGINAL gentle bedtime/moral story for kids aged 3-8 in {lang}, about 6 minutes narrated.
{topic}
Rules: Scene 1 is a fun hook. Nothing scary or violent. Exactly 36 scenes, each narration 25-35 words. End with a kind moral.
{SCHEMA_KIDS}"""


def run_kids(name):
    cfg = CHANNELS[name]
    rng = random.Random()
    day = datetime.date.today()
    mode = os.environ.get("MODE") or ("rhyme" if day.toordinal() % 2 else "story")
    hist = load_history(name)
    if os.environ.get("TOPIC"):
        topic = os.environ["TOPIC"]
    elif mode == "rhyme":
        topic = f"Theme: {rng.choice(RHYME_THEMES)}. Main character: {rng.choice(KIDS_HEROES)}."
    else:
        topic = (f"Hero: {rng.choice(KIDS_HEROES)}. Moral: {rng.choice(KIDS_THEMES)}. "
                 f"Setting: {rng.choice(KIDS_PLACES)}.")
    out = os.path.join("output", day.isoformat(), name)
    os.makedirs(os.path.join(out, "images"), exist_ok=True)

    print(f"[{name}] writing {mode}...")
    story = gemini(kids_prompt(cfg, mode, topic + " " + avoid_text(hist)))

    print(f"[{name}] images (slow)...")
    images = []
    for i, s in enumerate(story["scenes"]):
        p = os.path.join(out, "images", f"{i:02d}.jpg")
        make_image(f"{story['character']}. {s['image']}. {KIDS_STYLE}", p, seed=i + 1)
        images.append(p)
        time.sleep(3)
    with open(images[0], "rb") as a, open(os.path.join(out, "thumbnail.jpg"), "wb") as b:
        b.write(a.read())

    rate = "-15%" if mode == "rhyme" else "+0%"
    audio_lists = []
    for i, s in enumerate(story["scenes"]):
        ap = os.path.join(out, f"a{i}.mp3")
        tts(s["narration"], cfg["voice"], ap, rate=rate)
        audio_lists.append([ap])
    print(f"[{name}] building video...")
    assemble(images, audio_lists, out, repeat=3 if mode == "rhyme" else 1, short_mode="crop")
    write_info(out, story)
    save_history(name, story["title"])
    print(f"[{name}] done ->", out)


# ---------------------------------------------------------------- village channel
def pick_cast(rng):
    males = [k for k in art.FACES if k[0] == "m"]
    females = [k for k in art.FACES if k[0] == "f"]
    ids = rng.sample(males, rng.choice([2, 3])) + rng.sample(females, rng.choice([2, 3]))
    rng.shuffle(ids)
    dresses = art.pick_dresses(rng, len(ids))
    mn, fn, kn = MALE_NAMES[:], FEMALE_NAMES[:], KID_NAMES[:]
    for pool in (mn, fn, kn):
        rng.shuffle(pool)
    cast = {}
    for cid, dr in zip(ids, dresses):
        f = art.FACES[cid]
        pool = kn if f["age"] == "child" else (mn if f["gender"] == "m" else fn)
        cast[cid] = dict(id=cid, name=pool.pop(), gender=f["gender"], age=f["age"], dress=dr)
    return cast


def village_prompt(cast, topic, hist):
    cast_txt = json.dumps([{"id": c["id"], "name": c["name"], "gender": c["gender"], "age": c["age"]}
                           for c in cast.values()], ensure_ascii=False)
    return f"""Write an ORIGINAL Hindi cartoon story about Indian village life for a YouTube channel (audience 14+), about 8 minutes narrated.
Story idea: {topic}
CAST (use ONLY these characters, with exactly these names; each keeps the same name and role in the whole story; pick the roles that fit their gender and age): {cast_txt}
{avoid_text(hist)}
Rules:
- Scene 1 is a strong hook that creates curiosity or emotion. Add struggle, a surprising twist, and a satisfying ending with a moral.
- Exactly 40 scenes. In each scene the total of all lines is 30-45 words of simple spoken Hindi (Devanagari). Use short dialogue lines.
- Each line has "who": "narrator" or a cast id; "text": the Hindi words spoken. A character speaks only their own words.
- "present": the cast characters visible in that scene (max 4, include everyone who speaks) with an emotion from {art.EMOTIONS}.
- "background" must be one of {art.BACKGROUNDS}.
- No violence, gore, abuse, religion/caste/community insults or adult content.
Return JSON: {{"title": "catchy Hindi title", "description": "Hindi description", "tags": ["..."],
"scenes": [{{"background": "...", "present": [{{"id": "m1", "emotion": "happy"}}],
"lines": [{{"who": "narrator", "text": "..."}}]}}]}}"""


def clean_village(story, cast):
    scenes = []
    for sc in story["scenes"]:
        bg = sc.get("background")
        if bg not in art.BG_FUNCS:
            bg = "village_street"
        present = []
        for p in sc.get("present", []):
            if isinstance(p, str):
                p = {"id": p}
            if p.get("id") in cast and all(q["id"] != p["id"] for q in present):
                present.append({"id": p["id"], "emotion": p.get("emotion", "neutral")})
        lines = [dict(who=l.get("who", "narrator"), text=l["text"]) for l in sc.get("lines", []) if l.get("text")]
        if not lines:
            continue
        for l in lines:
            if l["who"] != "narrator" and l["who"] not in cast:
                l["who"] = "narrator"
            if l["who"] != "narrator" and all(q["id"] != l["who"] for q in present):
                present.append({"id": l["who"], "emotion": "neutral"})
        scenes.append(dict(background=bg, present=present[:4], lines=lines))
    if len(scenes) < 10:
        raise RuntimeError("Story too short, run again")
    return scenes


PITCH = {("m", "child"): 30, ("m", "young"): 6, ("m", "middle"): -2, ("m", "old"): -14,
         ("f", "child"): 22, ("f", "young"): 0, ("f", "middle"): -4, ("f", "old"): -10}


def village_voice(who, cast):
    if who == "narrator":
        return "hi-IN-MadhurNeural", "-6Hz"
    c = cast[who]
    voice = "hi-IN-MadhurNeural" if c["gender"] == "m" else "hi-IN-SwaraNeural"
    return voice, f"{PITCH[(c['gender'], c['age'])]:+d}Hz"


def run_village(name):
    rng = random.Random()
    day = datetime.date.today()
    hist = load_history(name)
    cast = pick_cast(rng)
    topic = os.environ.get("TOPIC") or f"{rng.choice(GENRES)}. A main hero idea: {rng.choice(JOBS)}."
    out = os.path.join("output", day.isoformat(), name)
    os.makedirs(os.path.join(out, "images"), exist_ok=True)

    print(f"[{name}] writing story... cast:", ", ".join(f"{c['name']}({c['id']})" for c in cast.values()))
    story = gemini(village_prompt(cast, topic, hist))
    scenes = clean_village(story, cast)

    print(f"[{name}] drawing scenes...")
    images = []
    for i, sc in enumerate(scenes):
        p = os.path.join(out, "images", f"{i:02d}.jpg")
        art.render_scene(sc["background"], sc["present"], cast).save(p, quality=92)
        images.append(p)
    best = max(range(min(10, len(scenes))), key=lambda i: (len(scenes[i]["present"]),
               any(x["emotion"] != "neutral" for x in scenes[i]["present"])))
    with open(images[best], "rb") as a, open(os.path.join(out, "thumbnail.jpg"), "wb") as b:
        b.write(a.read())

    print(f"[{name}] voices...")
    audio_lists = []
    for i, sc in enumerate(scenes):
        files = []
        for j, ln in enumerate(sc["lines"]):
            ap = os.path.join(out, f"a{i}_{j}.mp3")
            voice, pitch = village_voice(ln["who"], cast)
            tts(ln["text"], voice, ap, pitch=pitch)
            files.append(ap)
        audio_lists.append(files)

    print(f"[{name}] building video...")
    assemble(images, audio_lists, out, short_mode="letterbox")
    cast_txt = "\nCAST THIS VIDEO:\n" + "\n".join(f"{c['name']} = face {c['id']}" for c in cast.values())
    write_info(out, story, cast_txt)
    save_history(name, story["title"])
    print(f"[{name}] done ->", out)


def run_channel(name):
    (run_village if CHANNELS[name]["kind"] == "village" else run_kids)(name)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    for ch in (CHANNELS if arg == "all" else [arg]):
        run_channel(ch)
