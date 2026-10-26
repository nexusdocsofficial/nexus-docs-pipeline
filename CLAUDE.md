# Instructies voor Claude (Nexus Docs pipeline)

- Lees eerst `README.md`. Gebruik de tools in `pipeline/`; schrijf geen nieuwe eenmalige scripts als een tool bestaat. Verbeter liever de tool en commit dat.
- **Na elke wijziging van de voice-over:** draai `align_vo` opnieuw met **alle** opnames die in de definitieve VO zitten, en bouw daarna `shots.json`/de montage opnieuw. Nooit oude timestamps hergebruiken.
- **Vóór je een montage aan Thijs laat zien:** draai `qa_check`. Bij fouten: eerst oplossen en opnieuw controleren. Lever het rapport mee (kort: aantal fouten/waarschuwingen).
- Communiceer met Thijs in het Nederlands. Video's, titels en beschrijvingen zijn Engels.
- Media horen niet in git (zie `.gitignore`); die staan op de Mac in `~/flow-mcp-out/`.
- Spiegel na een commit de map `pipeline/`, `templates/`, `fonts/` naar de Mac: `~/flow-mcp-out/NexusDocs-tools/pipeline-repo/` (back-up als GitHub niet bereikbaar is).
- **Oplevering aan Thijs:** lange video → map `~/flow-mcp-out/NN-Onderwerp-UPLOAD/` (video, thumbnails, SRT, één `KOPIEER-MIJ.txt`). Shorts → **zelfstandig, zonder tussentijds akkoord**: zelf de 3 momenten kiezen, monteren, controleren en herstellen; aan het einde de map `NN-Onderwerp-SHORTS/` met de 3 mp4s (naam = letter + uploadmoment) en één `KOPIEER-MIJ.txt` via de chat (en op de Mac als die bereikbaar is). `shorts_preview` alleen op verzoek.
- **Na akkoord op de eindversie:** zet de eindversie in de cloud (README: 'Eindversie in de cloud zetten', tag `nexus-final-NN`). De Shorts-generator werkt daarmee zonder Mac en levert via de chat.
