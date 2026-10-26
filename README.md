# Nexus Docs pipeline

Vaste, geteste tools om een Nexus Docs-video te maken: van voice-over tot CapCut-project, eindcontrole, ondertiteling, uploadpakket en Shorts.
De stijlregels staan in het claude.ai-project (`claude/stijlgids-nexus-docs.md`); deze repository bevat de code.

## Per video: één map met vaste bestanden

`videos/NN-onderwerp/`

| Bestand | Inhoud |
|---|---|
| `words.json` | elk woord van de **definitieve** voice-over met start/eind (gemaakt door `align_vo`) |
| `shots.json` | beeldspoor: `n, start, end, kind (still/card/outro), src, anchor` (eerste woorden van de VO-zin) |
| `chapters.json` | `n, title, start` |
| `video.json` | titel, hook, samenvatting, bronnen, tags, hashtags, uploadmoment, thumbnail, vastgezette reactie |
| `shorts.json` | montage-configuratie voor de 3 Shorts |
| `shorts-upload.json` | per Short: upload (YYYY-MM-DD HH:MM), frame, title, description, tags, pinned_comment, instagram (Reel-tekst) |
| `qa-*.md` | rapporten van de eindcontrole |

Media (mp3, mp4, jpg) staan **niet** in de repository maar op de Mac in `~/flow-mcp-out/`.

## Stappen en opdrachten

| Stap | Opdracht |
|---|---|
| Woordtiming na **elke** VO-wijziging | `python3 -m pipeline.align_vo --source ruwe-vo.mp3 ruwe-vo-words.json [--source extra.mp3 extra-words.json …] --final vo-definitief.mp3 --out videos/NN/words.json` |
| Beeldenlijst + Flow-prompts | `python3 -m pipeline.beeldenlijst videos/NN/beelden.json videos/NN/words.json` (era `none@1905` = geen mensen, wel tijdgetrouwe schepen/gebouwen) |
| Storyboard (controle 3) | `python3 -m pipeline.storyboard videos/NN/prompts.json videos/NN/words.json videos/NN/beeld-bestanden.json <map-met-beelden> storyboard.pdf --title "NN Onderwerp"` |
| CapCut-project bouwen | `pipeline.build_capcut.build(name, shots, stems, out_dir)` (zie docstring) |
| **Eindcontrole (verplicht vóór tonen)** | `python3 -m pipeline.qa_check --words videos/NN/words.json --capcut draft_info.json --beeldenlijst beeldenlijst.md [--video final.mp4] [--srt subs.srt] [--chapters chapters.json] --out videos/NN/qa.md` |
| Pauzes in een VO uit één opname (alinea 0,7 s, hoofdstuk 1,8 s, geknipt op echte stilte) | `python3 -m pipeline.vo_pauses vo-script.txt raw.mp3 raw-words.json vo.mp3 videos/NN/words.json` |
| Ondertiteling | `python3 -m pipeline.make_srt videos/NN/words.json NN-en.srt` |
| Uploadpakket (beschrijving + hoofdstukken) | `python3 -m pipeline.describe videos/NN/video.json videos/NN/chapters.json videos/NN/upload.md` |
| **Uploadmap lange video** | `python3 -m pipeline.upload_folder long videos/NN/video.json videos/NN/chapters.json ~/flow-mcp-out/NN-Onderwerp-UPLOAD --srt NN-en.srt --thumbs a.jpg b.jpg [--video final.mp4]` |
| Voorbeeld per Short (alleen op verzoek) | `python3 -m pipeline.shorts_preview videos/NN/shorts-upload.json OUT A=a.mp4 B=b.mp4 C=c.mp4` |
| **Uploadmap Shorts** | `python3 -m pipeline.upload_folder shorts videos/NN/video.json videos/NN/shorts-upload.json ~/flow-mcp-out/NN-Onderwerp-SHORTS A=a.mp4 B=b.mp4 C=c.mp4` |
| Shorts | `python3 -m pipeline.make_shorts videos/NN/shorts.json [A B C]` |
| **Eindversie naar de cloud** (na akkoord op de eindversie) | zie hieronder |

### Eindversie in de cloud zetten (zodat Shorts zonder Mac kunnen)
1. Op de Mac (device_bash, past binnen 180 s voor ~10 min video): `ffmpeg -i "<CapCut-export>.mp4" -c:v libx264 -preset faster -crf 22 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart ~/flow-mcp-out/NN-<map>/final-web.mp4` (≈110 MB i.p.v. 800 MB). Achtergrondprocessen overleven een device_bash-call niet: in één call doen.
2. Creative Claw `get_upload_url` (type video, name `nexus-final-NN-<onderwerp>`, tags `["nexus-final", "nexus-final-NN"]`).
3. Vanaf de Mac: `curl -X PUT -H "Content-Type: video/mp4" -T final-web.mp4 "<uploadUrl>"` → 200.
4. `confirm_upload(asset_id)` → permanente cdn-URL. Terugvinden: `search_assets(tags=["nexus-final-NN"], type="video")`.
Vereist `*.r2.cloudflarestorage.com` op de domein-allowlist (ingesteld 22-10-2026).

### Wat de eindcontrole test
- **Sync:** elk beeld start binnen −0,6/+0,35 s van de eerste woorden van zijn VO-zin; beelden waarvan de zin niet (meer) in de VO staat.
- **Beeldduur:** stills 1,2–8,5 s (waarschuwing < 1,8 of > 6,5), hoofdstukkaart ≥ 4 s, outro ≥ 6 s.
- **Tijdlijn:** geen gaten of overlap, beeld loopt tot het einde van de audio.
- **Zwarte randen:** beeldverhouding + minimale zoom (CapCut), cropdetect (mp4).
- **Geluid:** −14 LUFS ± 1, geen stilte > 2,5 s buiten hoofdstukkaarten, piek.
- **Ondertiteling:** geen overlap, sluit aan op de VO, regellengte.

Exit code 1 = afgekeurd. Pas tonen aan Thijs als er **0 fouten** zijn (waarschuwingen mogen, maar noemen).

## Mappen
- `pipeline/` algemene tools · `templates/` CapCut-sjablonen · `fonts/` lettertypen voor Shorts · `legacy/` de oorspronkelijke scripts per video (alleen ter referentie)
