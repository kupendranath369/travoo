import React, { useMemo } from "react";
import { ScrollView } from "react-native";

import { Chip, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";

export const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function DateChips({ value, onChange, allowAny, days = 45, testID = "date" }: { value: string | null; onChange: (d: string | null) => void; allowAny?: boolean; days?: number; testID?: string }) {
  const { t, fmtDate } = useI18n();
  const list = useMemo(() => Array.from({ length: days }, (_, i) => isoDate(new Date(Date.now() + i * 86400000))), [days]);
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm, paddingVertical: space.xs }}>
      {allowAny ? <Chip testID={`${testID}-any`} label={t("search.any_date")} active={!value} onPress={() => onChange(null)} /> : null}
      {list.map((d, i) => (
        <Chip key={d} testID={`${testID}-${d}`} active={value === d} onPress={() => onChange(d)} label={i === 0 ? t("common.today") : i === 1 ? t("common.tomorrow") : fmtDate(d)} />
      ))}
    </ScrollView>
  );
}

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
const MINS = ["00", "15", "30", "45"];

export function TimeChips({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [h, m] = value.split(":");
  return (
    <>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm, paddingVertical: space.xs }}>
        {HOURS.map((x) => (
          <Chip key={x} testID={`hour-${x}`} label={`${x}h`} active={x === h} onPress={() => onChange(`${x}:${m}`)} />
        ))}
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm, paddingVertical: space.xs }}>
        {MINS.map((x) => (
          <Chip key={x} testID={`minute-${x}`} label={`:${x}`} active={x === m} onPress={() => onChange(`${h}:${x}`)} />
        ))}
      </ScrollView>
    </>
  );
}
