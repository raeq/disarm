# Language Reference

Complete reference of all 83 built-in language profiles, their transliteration rules, and test reference texts.

## Language Table

| Code | Language | Script | Region | Has Overrides |
|------|----------|--------|--------|:---:|
| `am` | Amharic | Ethiopic | African | Yes |
| `ar` | Arabic | Arabic | Middle Eastern | — |
| `as` | Assamese | Bengali | Indic | — |
| `ban` | Balinese | Balinese | Southeast Asian | — |
| `bax` | Bamum | Bamum | African | — |
| `bg` | Bulgarian | Cyrillic | European | Yes |
| `bn` | Bengali | Bengali | Indic | — |
| `bo` | Tibetan | Tibetan | Central Asian | — |
| `bug` | Buginese | Lontara | Southeast Asian | — |
| `ca` | Catalan | Latin | European | Yes |
| `chr` | Cherokee | Cherokee | Americas | — |
| `cjm` | Cham | Cham | Southeast Asian | — |
| `cop` | Coptic | Coptic | Middle Eastern | — |
| `cs` | Czech | Latin | European | — |
| `cy` | Welsh | Latin | European | — |
| `da` | Danish | Latin | European | — |
| `de` | German | Latin | European | Yes |
| `dv` | Dhivehi (Maldivian) | Thaana | South Asian | — |
| `el` | Greek | Greek | European | Yes |
| `es` | Spanish | Latin | European | Yes |
| `et` | Estonian | Latin | European | Yes |
| `fa` | Persian (Farsi) | Arabic | Middle Eastern | Yes |
| `fi` | Finnish | Latin | European | — |
| `fr` | French | Latin | European | Yes |
| `ga` | Irish | Latin | European | — |
| `gu` | Gujarati | Gujarati | Indic | — |
| `he` | Hebrew | Hebrew | Middle Eastern | — |
| `hi` | Hindi | Devanagari | Indic | — |
| `hr` | Croatian | Latin | European | — |
| `hu` | Hungarian | Latin | European | — |
| `hy` | Armenian | Armenian | Caucasian | — |
| `is` | Icelandic | Latin | European | Yes |
| `it` | Italian | Latin | European | Yes |
| `ja` | Japanese | Han/Kana | East Asian | Yes |
| `jv` | Javanese | Javanese | Southeast Asian | — |
| `ka` | Georgian | Georgian | Caucasian | — |
| `khb` | Tai Lue | New Tai Lue | Southeast Asian | — |
| `km` | Khmer | Khmer | Southeast Asian | — |
| `kn` | Kannada | Kannada | Indic | — |
| `ko` | Korean | Hangul | East Asian | — |
| `lis` | Lisu | Fraser/Lisu | East Asian | — |
| `lo` | Lao | Lao | Southeast Asian | — |
| `lt` | Lithuanian | Latin | European | — |
| `lv` | Latvian | Latin | European | — |
| `ml` | Malayalam | Malayalam | Indic | — |
| `mn` | Mongolian | Mongolian | Central Asian | — |
| `mni` | Meitei | Meetei Mayek | Indic | — |
| `mr` | Marathi | Devanagari | Indic | — |
| `mt` | Maltese | Latin | European | — |
| `my` | Myanmar (Burmese) | Myanmar | Southeast Asian | — |
| `ne` | Nepali | Devanagari | Indic | — |
| `nl` | Dutch | Latin | European | Yes |
| `no` | Norwegian | Latin | European | Yes |
| `nod` | Northern Thai | Tai Tham | Southeast Asian | — |
| `nqo` | N'Ko | N'Ko | African | — |
| `or` | Odia | Odia | Indic | — |
| `pa` | Punjabi | Gurmukhi | Indic | — |
| `pl` | Polish | Latin | European | — |
| `pt` | Portuguese | Latin | European | Yes |
| `ro` | Romanian | Latin | European | — |
| `ru` | Russian | Cyrillic | European | Yes |
| `sa` | Sanskrit | Devanagari | Indic | — |
| `sat` | Santali | Ol Chiki | Indic | — |
| `si` | Sinhala | Sinhala | South Asian | — |
| `sk` | Slovak | Latin | European | — |
| `sl` | Slovenian | Latin | European | — |
| `sq` | Albanian | Latin | European | — |
| `sr` | Serbian | Cyrillic | European | Yes |
| `su` | Sundanese | Sundanese | Southeast Asian | — |
| `sv` | Swedish | Latin | European | Yes |
| `syr` | Syriac | Syriac | Middle Eastern | — |
| `ta` | Tamil | Tamil | Indic | — |
| `tdd` | Tai Le | Tai Le | Southeast Asian | — |
| `te` | Telugu | Telugu | Indic | — |
| `th` | Thai | Thai | Southeast Asian | — |
| `tl` | Tagalog | Baybayin | Southeast Asian | — |
| `tr` | Turkish | Latin | European | Yes |
| `tzm` | Tamazight (Berber) | Tifinagh | African | — |
| `uk` | Ukrainian | Cyrillic | European | Yes |
| `vai` | Vai | Vai | African | — |
| `vi` | Vietnamese | Latin | Southeast Asian | Yes |
| `zh` | Chinese | Han | East Asian | — |

Languages marked **Yes** in "Has Overrides" have a dedicated TSV file that overrides the default transliteration table with language-specific rules. Languages with **—** rely entirely on the default Unicode transliteration tables.

## Reference Texts

Each language has a reference text used for integration testing. These texts are representative samples containing script-specific characters that exercise the transliteration rules.

| Code | Language | Reference Text |
|------|----------|---------------|
| `am` | Amharic | የኢትዮጵያ ፌዴራላዊ ዲሞክራሲያዊ ሪፐብሊክ... |
| `ar` | Arabic | المملكة العربية السعودية دولة عربية تقع في شبه الجزيرة العربية |
| `as` | Assamese | অসম ভাৰতৰ উত্তৰ পূৰ্বাঞ্চলৰ এখন ৰাজ্য |
| `bg` | Bulgarian | Република България е държава в Югоизточна Европа |
| `bn` | Bengali | গণপ্রজাতন্ত্রী বাংলাদেশ দক্ষিণ এশিয়ার একটি রাষ্ট্র |
| `bo` | Tibetan | བོད་རང་སྐྱོང་ལྗོངས་ནི་རྒྱ་ནག་གི་ཁོངས་གཏོགས |
| `ca` | Catalan | Catalunya és una comunitat autònoma d'Espanya |
| `cs` | Czech | Česká republika je stát ve střední Evropě |
| `cy` | Welsh | Cymru yw gwlad sy'n rhan o'r Deyrnas Unedig |
| `da` | Danish | København er Danmarks hovedstad og største by |
| `de` | German | Die Bundesrepublik Deutschland ist ein Bundesstaat in Mitteleuropa |
| `dv` | Dhivehi | ދިވެހިރާއްޖެ |
| `el` | Greek | Η Ελληνική Δημοκρατία είναι χώρα της νοτιοανατολικής Ευρώπης |
| `es` | Spanish | España es un país soberano transcontinental |
| `et` | Estonian | Eesti Vabariik on riik Põhja-Euroopas Läänemere ääres |
| `fa` | Persian | جمهوری اسلامی ایران کشوری در خاورمیانه است |
| `fi` | Finnish | Suomen tasavalta on valtio Pohjois-Euroopassa |
| `fr` | French | La République française est un État transcontinental |
| `ga` | Irish | Éire nó Poblacht na hÉireann is tír í |
| `gu` | Gujarati | ગુજરાત ભારતનું એક રાજ્ય છે જે ભારતના પશ્ચિમ ભાગમાં |
| `he` | Hebrew | מדינת ישראל היא מדינה במזרח התיכון |
| `hi` | Hindi | भारत गणराज्य दक्षिण एशिया में स्थित एक देश है |
| `hr` | Croatian | Republika Hrvatska je država u srednjoj Europi |
| `hu` | Hungarian | Magyarország közép-európai ország |
| `hy` | Armenian | Հայաստան Հանրապետություն Հայ երկիր |
| `is` | Icelandic | Ísland er eyríki á norðanverðum Atlantshafi |
| `it` | Italian | La Repubblica Italiana è uno Stato membro dell'Unione europea |
| `ja` | Japanese | 日本国は東アジアに位置する島国である |
| `jv` | Javanese | ꦐꦟꦪꦣꦨ |
| `ka` | Georgian | საქართველო სახელმწიფოა აღმოსავლეთ ევროპაში |
| `km` | Khmer | ព្រះរាជាណាចក្រកម្ពុជា ជាប្រទេសមួយ |
| `kn` | Kannada | ಕರ್ನಾಟಕ ದಕ್ಷಿಣ ಭಾರತದ ಒಂದು ರಾಜ್ಯ |
| `ko` | Korean | 대한민국은 동아시아에 있는 공화국이다 |
| `lo` | Lao | ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ |
| `lt` | Lithuanian | Lietuvos Respublika yra valstybė šiaurės Europoje |
| `lv` | Latvian | Latvijas Republika ir valsts Ziemeļeiropā |
| `ml` | Malayalam | കേരളം ഇന്ത്യയിലെ ഒരു സംസ്ഥാനമാണ് |
| `mn` | Mongolian | ᠮᠣᠩᠭᠣᠯ |
| `mr` | Marathi | महाराष्ट्र हे भारतातील एक राज्य आहे |
| `mt` | Maltese | Ir-Repubblika ta' Malta hija stat gżejjer fil-Mediterran |
| `my` | Myanmar | မြန်မာနိုင်ငံသည် အရှေ့တောင်အာရှတွင် |
| `ne` | Nepali | नेपाल एशियाको एक स्वतन्त्र देश हो |
| `nl` | Dutch | Het Koninkrijk der Nederlanden is een staat in West-Europa |
| `no` | Norwegian | Kongeriket Norge er et nordisk land i Skandinavia |
| `or` | Odia | ଓଡ଼ିଶା ଭାରତର ପୂର୍ବ ଉପକୂଳରେ ଅବସ୍ଥିତ |
| `pa` | Punjabi | ਪੰਜਾਬ ਭਾਰਤ ਦਾ ਇੱਕ ਰਾਜ ਹੈ |
| `pl` | Polish | Rzeczpospolita Polska jest państwem w Europie Środkowej |
| `pt` | Portuguese | A República Portuguesa é um país situado no sudoeste da Europa |
| `ro` | Romanian | România este un stat situat în sud-estul Europei |
| `ru` | Russian | Российская Федерация является демократическим федеративным государством |
| `sa` | Sanskrit | संस्कृतम् जगतः एका प्राचीनतमा भाषा |
| `si` | Sinhala | ශ්‍රී ලංකා ප්‍රජාතාන්ත්‍රික සමාජවාදී ජනරජය |
| `sk` | Slovak | Slovenská republika je štát v strednej Európe |
| `sl` | Slovenian | Republika Slovenija je država v srednji Evropi |
| `sq` | Albanian | Republika e Shqipërisë është një shtet në Europën Juglindore |
| `sr` | Serbian | Београд → Beograd |
| `sv` | Swedish | Konungariket Sverige är ett nordiskt land på Skandinaviska halvön |
| `ta` | Tamil | தமிழ்நாடு இந்தியாவின் தெற்கே அமைந்துள்ள மாநிலம் |
| `te` | Telugu | తెలుగు భాష ద్రావిడ భాషా కుటుంబానికి చెందిన భాష |
| `th` | Thai | ประเทศไทยเป็นรัฐชาติอันตั้งอยู่ในเอเชียตะวันออกเฉียงใต้ |
| `tr` | Turkish | Türkiye Cumhuriyeti Avrupa ile Asya arasında yer alan bir ülkedir |
| `uk` | Ukrainian | Україна є державою у Східній та Центральній Європі |
| `vi` | Vietnamese | Cộng hòa xã hội chủ nghĩa Việt Nam là một quốc gia |
| `zh` | Chinese | 中华人民共和国是位于东亚的社会主义国家 |

## Language-Specific Transliteration Rules

The following sections document the exact character-level overrides applied by each language profile. Languages without a dedicated section rely entirely on the default Unicode transliteration tables (accent stripping, script-specific tables, etc.).

### Amharic (`am`)

Based on BGN/PCGN romanization for Amharic. Three categories of overrides:

**ጸ series — tsade merger (U+1338–U+133F):**

| Character | Unicode | Default | Override | Notes |
|-----------|---------|---------|----------|-------|
| ጸ | U+1338 | tse | se | Ejective /sʼ/ in Amharic, not /ts/ |
| ጹ | U+1339 | tsu | su | |
| ጺ | U+133A | tsi | si | |
| ጻ | U+133B | tsa | sa | |
| ጼ | U+133C | tse | se | |
| ጽ | U+133D | ts | s | |
| ጾ | U+133E | tso | so | |
| ጿ | U+133F | tswa | swa | |

**ፀ series — tsade merger (U+1340–U+1347):**

| Character | Unicode | Default | Override | Notes |
|-----------|---------|---------|----------|-------|
| ፀ | U+1340 | tse | se | ጸ/ፀ merger in modern Amharic |
| ፁ | U+1341 | tsu | su | |
| ፂ | U+1342 | tsi | si | |
| ፃ | U+1343 | tsa | sa | |
| ፄ | U+1344 | tse | se | |
| ፅ | U+1345 | ts | s | |
| ፆ | U+1346 | tso | so | |
| ፇ | U+1347 | tswa | swa | |

**ዐ series — pharyngeal marking (U+12D0–U+12D6):**

| Character | Unicode | Default | Override | Notes |
|-----------|---------|---------|----------|-------|
| ዐ | U+12D0 | e | 'e | Pharyngeal distinct from glottal stop (አ) |
| ዑ | U+12D1 | u | 'u | |
| ዒ | U+12D2 | i | 'i | |
| ዓ | U+12D3 | a | 'a | |
| ዔ | U+12D4 | e | 'e | |
| ዕ | U+12D5 | e | 'e | |
| ዖ | U+12D6 | o | 'o | |

### Bulgarian (`bg`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ъ | U+042A | A | Hard sign |
| ъ | U+044A | a | Hard sign (lowercase) |
| Щ | U+0429 | Sht | Shta |
| щ | U+0449 | sht | Shta (lowercase) |

### Catalan (`ca`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| · | U+00B7 | *(empty)* | Interpunct (ela geminada separator removed) |

### German (`de`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ä | U+00C4 | Ae | Umlaut |
| Ö | U+00D6 | Oe | Umlaut |
| Ü | U+00DC | Ue | Umlaut |
| ä | U+00E4 | ae | Umlaut (lowercase) |
| ö | U+00F6 | oe | Umlaut (lowercase) |
| ü | U+00FC | ue | Umlaut (lowercase) |
| ẞ | U+1E9E | SS | Capital sharp s |

### Greek (`el`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Η | U+0397 | I | Eta |
| η | U+03B7 | i | Eta (lowercase) |
| Υ | U+03A5 | Y | Upsilon |
| υ | U+03C5 | y | Upsilon (lowercase) |
| Χ | U+03A7 | Ch | Chi |
| χ | U+03C7 | ch | Chi (lowercase) |

### Spanish (`es`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| ¡ | U+00A1 | ! | Inverted exclamation mark |
| ¿ | U+00BF | ? | Inverted question mark |

### Estonian (`et`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ä | U+00C4 | Ae | |
| ä | U+00E4 | ae | |
| Ö | U+00D6 | Oe | |
| ö | U+00F6 | oe | |
| Ü | U+00DC | Ue | |
| ü | U+00FC | ue | |

### Persian (`fa`)

Based on BGN/PCGN 1958 romanization system with ASCII output.

**Consonants:**

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| ب | U+0628 | b | |
| پ | U+067E | p | Persian-specific |
| ت | U+062A | t | |
| ث | U+062B | s | Persian pronunciation (Arabic: th) |
| ج | U+062C | j | |
| چ | U+0686 | ch | Persian-specific |
| ح | U+062D | h | |
| خ | U+062E | kh | |
| د | U+062F | d | |
| ذ | U+0630 | z | Persian pronunciation (Arabic: dh) |
| ر | U+0631 | r | |
| ز | U+0632 | z | |
| ژ | U+0698 | zh | Persian-specific |
| س | U+0633 | s | |
| ش | U+0634 | sh | |
| ص | U+0635 | s | |
| ض | U+0636 | z | Persian pronunciation (Arabic: d) |
| ط | U+0637 | t | |
| ظ | U+0638 | z | |
| ع | U+0639 | ' | Ain |
| غ | U+063A | gh | |
| ف | U+0641 | f | |
| ق | U+0642 | q | |
| ک | U+06A9 | k | Persian kaf |
| گ | U+06AF | g | Persian-specific |
| ل | U+0644 | l | |
| م | U+0645 | m | |
| ن | U+0646 | n | |
| و | U+0648 | v | Consonantal default |
| ه | U+0647 | h | |
| ی | U+06CC | y | Farsi yeh |
| ك | U+0643 | k | Arabic kaf fallback |

**Vowels and special characters:**

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| ا | U+0627 | a | Alef |
| آ | U+0622 | a | Alef-madda |
| ء | U+0621 | ' | Hamza |
| أ | U+0623 | a | Alef with hamza above |
| إ | U+0625 | e | Alef with hamza below |
| ؤ | U+0624 | ' | Waw with hamza (glottal stop) |
| ئ | U+0626 | ' | Yeh with hamza (glottal stop) |
| ة | U+0629 | e | Taa marbuta |
| ى | U+0649 | a | Alef maqsura |
| ي | U+064A | y | Arabic yaa |
| ۀ | U+06C0 | -e | Izafe |
| ہ | U+06C1 | h | Heh goal |

**Diacritics:**

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| فتحه | U+064E | a | Fathah |
| کسره | U+0650 | e | Kasra |
| ضمه | U+064F | o | Damma |
| سکون | U+0652 | *(empty)* | Sukun — suppress vowel |
| شدّه | U+0651 | *(empty)* | Shadda — gemination |

**Digits:** ۰–۹ (U+06F0–U+06F9) → 0–9

**Punctuation:** ، → `,`  ؛ → `;`  ؟ → `?`  ۔ → `.`

### French (`fr`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Œ | U+0152 | OE | Ligature |
| œ | U+0153 | oe | Ligature (lowercase) |
| Æ | U+00C6 | AE | Ligature |
| æ | U+00E6 | ae | Ligature (lowercase) |

### Icelandic (`is`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ð | U+00D0 | Dh | Eth |
| ð | U+00F0 | dh | Eth (lowercase) |
| Þ | U+00DE | Th | Thorn |
| þ | U+00FE | th | Thorn (lowercase) |
| Æ | U+00C6 | Ae | |
| æ | U+00E6 | ae | |

### Italian (`it`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| ª | U+00AA | a | Feminine ordinal indicator |
| º | U+00BA | o | Masculine ordinal indicator |

### Japanese (`ja`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| ー | U+30FC | *(empty)* | Chōonpu (prolonged sound mark) removed |

Japanese uses the default Hiragana/Katakana → Hepburn tables and Han → Chinese pinyin fallback. Only the prolonged sound mark is overridden.

### Dutch (`nl`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ĳ | U+0132 | IJ | Ligature |
| ĳ | U+0133 | ij | Ligature (lowercase) |

### Norwegian (`no`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Å | U+00C5 | Aa | |
| å | U+00E5 | aa | |
| Ø | U+00D8 | Oe | |
| ø | U+00F8 | oe | |
| Æ | U+00C6 | Ae | |
| æ | U+00E6 | ae | |

Both `"no"` and `"nb"` (Bokmål) map to the same profile. `"nn"` (Nynorsk) also uses the same mappings.

### Portuguese (`pt`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| ª | U+00AA | a | Feminine ordinal indicator |
| º | U+00BA | o | Masculine ordinal indicator |

### Russian (`ru`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ё | U+0401 | Yo | |
| ё | U+0451 | yo | |
| Й | U+0419 | Y | Short I |
| й | U+0439 | y | Short I (lowercase) |
| Ъ | U+042A | " | Hard sign |
| ъ | U+044A | " | Hard sign (lowercase) |
| Ь | U+042C | ' | Soft sign |
| ь | U+044C | ' | Soft sign (lowercase) |
| Э | U+042D | E | Reversed E |
| э | U+044D | e | Reversed E (lowercase) |
| Ю | U+042E | Yu | |
| ю | U+044E | yu | |
| Я | U+042F | Ya | |
| я | U+044F | ya | |

### Serbian (`sr`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ђ | U+0402 | Dj | Dje |
| ђ | U+0452 | dj | Dje (lowercase) |
| Ћ | U+040B | C | Tshe |
| ћ | U+045B | c | Tshe (lowercase) |
| Џ | U+040F | Dz | Dzhe |
| џ | U+045F | dz | Dzhe (lowercase) |
| Љ | U+0409 | Lj | Lje |
| љ | U+0459 | lj | Lje (lowercase) |
| Њ | U+040A | Nj | Nje |
| њ | U+045A | nj | Nje (lowercase) |
| Ј | U+0408 | J | Je |
| ј | U+0458 | j | Je (lowercase) |
| Й | U+0419 | Y | Short I |
| й | U+0439 | y | Short I (lowercase) |

### Swedish (`sv`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Ä | U+00C4 | Ae | |
| ä | U+00E4 | ae | |
| Ö | U+00D6 | Oe | |
| ö | U+00F6 | oe | |

### Turkish (`tr`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| İ | U+0130 | I | Dotted capital I |
| ı | U+0131 | i | Dotless lowercase i |
| Ğ | U+011E | G | Breve |
| ğ | U+011F | g | Breve (lowercase) |
| Ş | U+015E | S | Cedilla |
| ş | U+015F | s | Cedilla (lowercase) |

### Ukrainian (`uk`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Г | U+0413 | H | Ukrainian /h/ sound (Russian: G) |
| г | U+0433 | h | |
| Ґ | U+0490 | G | Hard /g/ sound |
| ґ | U+0491 | g | |
| Є | U+0404 | Ye | Ukrainian Ye |
| є | U+0454 | ye | |
| Ї | U+0407 | I | Yi |
| ї | U+0457 | i | |
| І | U+0406 | I | Ukrainian I |
| і | U+0456 | i | |
| И | U+0418 | Y | Ukrainian Y (Russian: I) |
| и | U+0438 | y | |
| Ь | U+042C | ' | Soft sign |
| ь | U+044C | ' | Soft sign (lowercase) |

### Vietnamese (`vi`)

| Character | Unicode | Replacement | Notes |
|-----------|---------|-------------|-------|
| Đ | U+0110 | D | D with stroke |
| đ | U+0111 | d | D with stroke (lowercase) |
| Ơ | U+01A0 | O | O with horn |
| ơ | U+01A1 | o | O with horn (lowercase) |
| Ư | U+01AF | U | U with horn |
| ư | U+01B0 | u | U with horn (lowercase) |
