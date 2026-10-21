// =====================================================================
//  PROV, LÄXOR OCH ANNAT – skriv in här
// =====================================================================
//  En rad per sak, mellan [ och ] längst ner. Fälten:
//
//    datum : "ÅÅÅÅ-MM-DD"                       (måste finnas)
//    typ   : "prov", "läxa" eller något annat (t.ex. "redovisning")
//    amne  : "Matte"                            (valfritt)
//    text  : "Kapitel 4 – geometri"             (valfritt)
//    klass : "9A" eller "9B"                    (valfritt – tomt = båda klasserna)
//    till  : "ÅÅÅÅ-MM-DD"                       (valfritt – för saker som varar flera dagar)
//
//  Ta bort // framför raderna nedan för att prova, och kopiera/ändra för egna.
// =====================================================================
const KALENDER = [
  // { datum: "2026-10-28", typ: "prov",  amne: "Matte",   text: "Kapitel 4 – geometri" },
  // { datum: "2026-10-27", typ: "läxa",  amne: "Svenska", text: "Läs kap. 3", klass: "9B" },
  // { datum: "2026-11-02", till: "2026-11-04", typ: "Studiedag", text: "Ingen skola" },
];
