import { ClockTimePicker } from "@/src/components/ClockTimePicker";
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

/** Time selection: digital hour/minute picker with AM/PM and quick presets. */
export function TimeChips({ value, onChange, testID = "time-picker" }: { value: string; onChange: (v: string) => void; testID?: string }) {
  return <ClockTimePicker testID={testID} label="" value={value} onChange={onChange} />;
}
