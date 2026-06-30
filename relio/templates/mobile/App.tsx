import { useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  Button,
  FlatList,
  StyleSheet,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { RelioClient } from "./src/sdk/client";
import type { MemoryRecord } from "./src/sdk/types";

// A device can't reach the host's "localhost" — set this to your machine's LAN
// IP (e.g. http://192.168.1.20:8000) when running on a phone.
const client = new RelioClient("http://localhost:8000");

export default function App() {
  const [q, setQ] = useState("");
  const [draft, setDraft] = useState("");
  const [results, setResults] = useState<MemoryRecord[]>([]);

  async function search() {
    const res = await client.searchMemory({ q });
    setResults(res.results);
  }

  async function add() {
    const content = draft.trim();
    if (!content) return;
    setDraft("");
    await client.addMemory({ content });
    await search();
  }

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Relio</Text>
      <View style={styles.row}>
        <TextInput
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder="Add a memory…"
        />
        <Button title="Add" onPress={add} />
      </View>
      <View style={styles.row}>
        <TextInput
          style={styles.input}
          value={q}
          onChangeText={setQ}
          placeholder="Search…"
        />
        <Button title="Search" onPress={search} />
      </View>
      <FlatList
        data={results}
        keyExtractor={(r) => r.id!}
        renderItem={({ item }) => <Text style={styles.item}>• {item.content}</Text>}
      />
      <StatusBar style="auto" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  title: { fontSize: 22, fontWeight: "600" },
  row: { flexDirection: "row", gap: 8, alignItems: "center" },
  input: { flex: 1, borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 8 },
  item: { paddingVertical: 6 },
});
