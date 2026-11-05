import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { storage } from "@/src/utils/storage";

import as from "./locales/as.json";
import bn from "./locales/bn.json";
import brx from "./locales/brx.json";
import doi from "./locales/doi.json";
import en from "./locales/en.json";
import gu from "./locales/gu.json";
import hi from "./locales/hi.json";
import kn from "./locales/kn.json";
import kok from "./locales/kok.json";
import ks from "./locales/ks.json";
import mai from "./locales/mai.json";
import ml from "./locales/ml.json";
import mni from "./locales/mni.json";
import mr from "./locales/mr.json";
import ne from "./locales/ne.json";
import or from "./locales/or.json";
import pa from "./locales/pa.json";
import sa from "./locales/sa.json";
import sat from "./locales/sat.json";
import sd from "./locales/sd.json";
import ta from "./locales/ta.json";
import te from "./locales/te.json";
import ur from "./locales/ur.json";

type Dict = Record<string, string>;
const DICTS: Record<string, Dict> = { en, hi, bn, te, mr, ta, ur, gu, kn, or, ml, pa, as, mai, sa, ks, kok, ne, sd, mni, brx, doi, sat };

export type Language = {
  code: string;
  native: string;
  english: string;
  rtl?: boolean;
  status: "reviewed" | "ai" | "planned";
};

// 22 Eighth-Schedule languages + English. "planned" = architecture ready, no translations yet.
export const LANGUAGES: Language[] = [
  { code: "en", native: "English", english: "English", status: "reviewed" },
  { code: "hi", native: "हिन्दी", english: "Hindi", status: "ai" },
  { code: "bn", native: "বাংলা", english: "Bengali", status: "ai" },
  { code: "te", native: "తెలుగు", english: "Telugu", status: "ai" },
  { code: "mr", native: "मराठी", english: "Marathi", status: "ai" },
  { code: "ta", native: "தமிழ்", english: "Tamil", status: "ai" },
  { code: "ur", native: "اردو", english: "Urdu", rtl: true, status: "ai" },
  { code: "gu", native: "ગુજરાતી", english: "Gujarati", status: "ai" },
  { code: "kn", native: "ಕನ್ನಡ", english: "Kannada", status: "ai" },
  { code: "or", native: "ଓଡ଼ିଆ", english: "Odia", status: "ai" },
  { code: "ml", native: "മലയാളം", english: "Malayalam", status: "ai" },
  { code: "pa", native: "ਪੰਜਾਬੀ", english: "Punjabi", status: "ai" },
  { code: "as", native: "অসমীয়া", english: "Assamese", status: "ai" },
  { code: "mai", native: "मैथिली", english: "Maithili", status: "ai" },
  { code: "sa", native: "संस्कृतम्", english: "Sanskrit", status: "ai" },
  { code: "ks", native: "کٲشُر", english: "Kashmiri", rtl: true, status: "ai" },
  { code: "kok", native: "कोंकणी", english: "Konkani", status: "ai" },
  { code: "ne", native: "नेपाली", english: "Nepali", status: "ai" },
  { code: "sd", native: "سنڌي", english: "Sindhi", rtl: true, status: "ai" },
  { code: "mni", native: "ꯃꯤꯇꯩꯂꯣꯟ", english: "Manipuri (Meitei)", status: "ai" },
  { code: "brx", native: "बड़ो", english: "Bodo", status: "ai" },
  { code: "doi", native: "डोगरी", english: "Dogri", status: "ai" },
  { code: "sat", native: "ᱥᱟᱱᱛᱟᱲᱤ", english: "Santali", status: "ai" },
  { code: "bho", native: "भोजपुरी", english: "Bhojpuri", status: "planned" },
  { code: "tcy", native: "ತುಳು", english: "Tulu", status: "planned" },
  { code: "raj", native: "राजस्थानी", english: "Rajasthani", status: "planned" },
  { code: "hne", native: "छत्तीसगढ़ी", english: "Chhattisgarhi", status: "planned" },
  { code: "bgc", native: "हरियाणवी", english: "Haryanvi", status: "planned" },
  { code: "kha", native: "Khasi", english: "Khasi", status: "planned" },
  { code: "grt", native: "Garo", english: "Garo", status: "planned" },
  { code: "lus", native: "Mizo ṭawng", english: "Mizo", status: "planned" },
  { code: "trp", native: "Kokborok", english: "Kokborok", status: "planned" },
  { code: "bhb", native: "भीली", english: "Bhili", status: "planned" },
];

const LATIN = new Set(["en", "kha", "grt", "lus", "trp"]);
const LANG_KEY = "travoo_lang";

type Ctx = {
  lang: string;
  ready: boolean;
  chosen: boolean;
  rtl: boolean;
  latin: boolean;
  setLang: (code: string) => Promise<void>;
  t: (key: string, params?: Record<string, string | number>) => string;
  fmtDate: (iso: string, opts?: Intl.DateTimeFormatOptions) => string;
};

const I18nContext = createContext<Ctx | null>(null);

export const inr = (n: number) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState("en");
  const [chosen, setChosen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    storage.getItem(LANG_KEY, "").then((v) => {
      if (v && DICTS[v as string]) {
        setLangState(v as string);
        setChosen(true);
      }
      setReady(true);
    });
  }, []);

  const setLang = useCallback(async (code: string) => {
    if (!DICTS[code]) return;
    setLangState(code);
    setChosen(true);
    await storage.setItem(LANG_KEY, code);
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      let s = DICTS[lang]?.[key] ?? (en as Dict)[key] ?? key;
      if (params) for (const [k, v] of Object.entries(params)) s = s.replace(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );

  const fmtDate = useCallback(
    (iso: string, opts: Intl.DateTimeFormatOptions = { weekday: "short", day: "numeric", month: "short" }) => {
      const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
      try {
        return new Intl.DateTimeFormat(`${lang}-IN`, opts).format(d);
      } catch {
        return new Intl.DateTimeFormat("en-IN", opts).format(d);
      }
    },
    [lang],
  );

  const value = useMemo(
    () => ({
      lang,
      ready,
      chosen,
      rtl: !!LANGUAGES.find((l) => l.code === lang)?.rtl,
      latin: LATIN.has(lang),
      setLang,
      t,
      fmtDate,
    }),
    [lang, ready, chosen, setLang, t, fmtDate],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const c = useContext(I18nContext);
  if (!c) throw new Error("useI18n outside provider");
  return c;
}
