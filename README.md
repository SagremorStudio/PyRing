# PyRing – iskolai csengető program

Automatikus iskolai csengető Pythonban (PySide6 + pygame).

A program a nap folyamán magától megszólaltatja a jelző-, be- és kicsengetést, a szünetek zenéjét és a tűzriadó jelzést. Egész héten futhat, felügyelet nélkül.



<img width="1145" height="695" alt="screenshot" src="https://github.com/user-attachments/assets/91d42f38-ca02-48f4-b27f-7d63d46e9d13" />




## Funkciók

- **8 órás csengetési rend**, óránként három csengetéssel: jelző csengő, becsengetés, kicsengetés
- **Két rend között váltás** egy gombnyomással: *Normál* és *Rövid* csengetés. A rendek időpontjai szerkeszthetők, váltáskor a szerkesztett értékek nem vesznek el
- **Pipa (✓)** a csengetések mellett: csak akkor jelenik meg, ha az adott hang ténylegesen megszólalt. Az utolsó csengetés után egy perccel az összes pipa törlődik, így az új napot üres lappal kezdi
- **Szünet - Hanganyag lejátszás**: mind a 7 szünethez külön időpont és hangfájl, kézi lejátszás (P) és leállítás (S) gombbal, a lejátszási pozíció kijelzésével
- **Tűzriadó**: időzített vagy kézi indítás, leállítás, saját hangfájl. Amíg a tűzriadó szól, a többi csengetés kimarad, hogy ne vágjon bele
- **Kézi csengetés**: a jelző-, be- és kicsengetés hangja bármikor külön lejátszható
- **Alap hangok és óránkénti felülírás**: egy alap hang minden csengetéshez, de bármelyik csengetéshez megadható külön hang
- **Művelet napló**: időbélyeggel mutatja, mi szólalt meg, mi maradt ki, és minden hibát (például hiányzó hangfájl)
- **Kimaradás-védelem**: ha egy másodperces ellenőrzés kimarad (például a gép egy pillanatra lefagy), a csengetés 10 másodpercen belül még megszólal
- **Kilépés megerősítéssel**: a bezárt program nem csenget, ezért kilépés előtt rákérdez. Kilépéskor a beállításokat automatikusan menti
- **Régi beállítások átvétele**: az első indításkor beolvassa a Pascal verzió `sulics_multi.ini` és `sulics.ini` fájljait

## Telepítés

Python 3.10 vagy újabb szükséges.

```bash
pip install -r requirements.txt
python pyring.py
```

## Mappa szerkezet

```
pyring.py
requirements.txt
Sound/                 <- a hangfájlok (mp3, wav, ogg)
    jelzo.mp3
    becseng.mp3
    kicseng.mp3
    tuzriado3p.mp3
pring_config.json      <- automatikusan jön létre
```

A `Sound` mappát a programmal egy könyvtárban kell tárolni. A hangfájlok megadhatók abszolút útvonallal is, ilyenkor nem kell a `Sound` mappában lenniük.

## Használat

### Csengetési rend

A bal oldali táblázat mutatja az órák időpontjait (jelző, be, ki). Az időpontok közvetlenül szerkeszthetők. A `00:00:00` érték azt jelenti, hogy az adott csengetés ki van kapcsolva (a Rövid rend például nem használ jelző csengőt).

A jobb oldali **Rövid csengetés** és **Normál csengetés** gombbal lehet rendet váltani. Az aktív rend neve a táblázat alatt látható.

### Hangok

- Az alsó három sorban az alap jelző-, be- és kicsengetés hangja állítható, és a **Lejátszás** gombbal próbálható ki
- Egy adott csengetéshez külön hangot a `pring_config.json` fájlban az `ora_hangok` mezővel lehet megadni. A kulcs `<óra>_<fajta>` alakú:

```json
"ora_hangok": {
  "3_be": "masik_becsengetes.mp3",
  "8_ki": "utolso_kicsengetes.mp3"
}
```

Ha egy csengetéshez nincs külön hang megadva, az alap hang szólal meg.

### Szünet - Hanganyag lejátszás

A középső részen 7 sor található. Soronként:

| Elem | Funkció |
|---|---|
| 📂 | hangfájl kiválasztása |
| időpont | automatikus indítás ideje (`00:00:00` = kikapcsolva) |
| **P** / **S** | kézi lejátszás / leállítás |
| számláló | a lejátszott idő |

### Tűzriadó

A jobb felső részen állítható be az időpont és a hang. A **Tűzriadó jelzés** gomb azonnal elindítja, a **Tűzriadó leállítás** leállítja. Tűzriadó alatt a többi automatikus csengetés kimarad, és a naplóban "Kihagyva" bejegyzés jelzi.

### Mentés

A **Beállítások mentése** gomb a `pring_config.json` fájlba menti az időpontokat, hangokat, az aktív rendet és a szünet- és tűzriadó-beállításokat. Kilépéskor a program automatikusan ment.

## A csengetés működése

- A program negyedmásodpercenként ellenőrzi az időt, és minden eseményt naponta egyszer szólaltat meg
- Egyszerre egy hang szól: az új hang leváltja az előzőt, tehát a csengetés félbeszakítja a szünetzenét
- A hiányzó vagy hibás hangfájlt a napló jelzi, és az adott csengetés mellé nem kerül pipa
- Éjfélkor és rendváltáskor az események újra élesednek, a pipák törlődnek

## Beállítófájl

A `pring_config.json` szerkezete:

```json
{
  "aktiv_rend": "normal",
  "rendek": {
    "normal": [["07:42:00", "07:45:00", "08:30:00"], "..."],
    "rovid":  [["00:00:00", "07:45:00", "08:15:00"], "..."]
  },
  "hangok": { "jelzo": "jelzo.mp3", "be": "becseng.mp3", "ki": "kicseng.mp3" },
  "ora_hangok": {},
  "szunetek": [{ "ido": "00:00:00", "fajl": "" }],
  "tuzriado": { "ido": "09:05:00", "fajl": "tuzriado3p.mp3" }
}
```

A `rendek` alatt óránként egy `[jelző, be, ki]` hármas szerepel.

## Futtatható (exe) készítése

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile pring.py
```

A kész program a `dist` mappában jön létre. A `Sound` mappát mellé kell másolni. Egyes víruskeresők a PyInstallerrel készült programokra tévesen riasztanak, ilyenkor érdemes kivételt felvenni.

### Automatikus indítás Windowson

Az exe (vagy egy parancsikonja) a `Win + R` után megnyíló `shell:startup` mappába másolva a gép indításakor magától elindul.

## Fejlesztési ötletek

- Hétvégék és szünetnapok kihagyása
- Több csengetési rend (például rövidített napokhoz) és naptár alapú automatikus váltás
- Óránkénti hangok szerkesztése a felületről

## Licenc

MIT License
