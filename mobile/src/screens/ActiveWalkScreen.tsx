import React, { useEffect, useRef, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import * as Location from 'expo-location';
import { Audio } from 'expo-av';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import { getDownloadedTour, queueSessionEvent, getQueuedEvents, clearQueuedEvents } from '../api/offlineStorage';
import { distanceMeters } from '../api/geo';
import { sessionsApi } from '../api/endpoints';
import { uuidv4 } from '../api/uuid';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';
import type { DownloadedTour, StopWithAudio } from '../types';

type Props = NativeStackScreenProps<AppStackParamList, 'ActiveWalk'>;

export function ActiveWalkScreen({ route, navigation }: Props) {
  const { tourId, sessionId } = route.params;
  const [tour, setTour] = useState<DownloadedTour | null>(null);
  const [visitedStopIds, setVisitedStopIds] = useState<Set<string>>(new Set());
  const [activeStop, setActiveStop] = useState<StopWithAudio | null>(null);
  const [nearestDistance, setNearestDistance] = useState<number | null>(null);
  const [completing, setCompleting] = useState(false);

  const soundRef = useRef<Audio.Sound | null>(null);
  const locationSubscription = useRef<Location.LocationSubscription | null>(null);
  const visitedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const downloaded = await getDownloadedTour(tourId);
      if (!downloaded) return;
      setTour(downloaded);

      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true, staysActiveInBackground: true });

      locationSubscription.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.High, timeInterval: 3000, distanceInterval: 5 },
        (position) => {
          if (cancelled) return;
          handlePositionUpdate(downloaded, position.coords.latitude, position.coords.longitude);
        }
      );
    })();

    // Best-effort sync of anything queued while offline — runs on mount and
    // could also be wired to a periodic timer / app-foreground event.
    flushQueuedEvents();

    return () => {
      cancelled = true;
      locationSubscription.current?.remove();
      soundRef.current?.unloadAsync();
    };
  }, [tourId]);

  async function handlePositionUpdate(downloaded: DownloadedTour, lat: number, lng: number) {
    const nextStop = downloaded.tourPackage.stops.find((s) => !visitedRef.current.has(s.id));
    if (!nextStop) return;

    const distance = distanceMeters(lat, lng, parseFloat(nextStop.lat), parseFloat(nextStop.lng));
    setNearestDistance(distance);

    if (distance <= nextStop.trigger_radius_m) {
      await handleArrivedAtStop(downloaded, nextStop);
    }
  }

  async function handleArrivedAtStop(downloaded: DownloadedTour, stop: StopWithAudio) {
    if (visitedRef.current.has(stop.id)) return;
    visitedRef.current.add(stop.id);
    setVisitedStopIds(new Set(visitedRef.current));
    setActiveStop(stop);

    await queueSessionEvent(sessionId, {
      client_event_id: uuidv4(),
      stop_id: stop.id,
      event_type: 'arrived',
      occurred_at: new Date().toISOString(),
    });

    await playStopAudio(downloaded, stop);
    await flushQueuedEvents();

    const allVisited = downloaded.tourPackage.stops.every((s) => visitedRef.current.has(s.id));
    if (allVisited) {
      await handleCompleteWalk();
    }
  }

  async function playStopAudio(downloaded: DownloadedTour, stop: StopWithAudio) {
    try {
      await soundRef.current?.unloadAsync();
      const localUri = downloaded.audioLocalPaths[stop.id] || stop.audio_url;
      const { sound } = await Audio.Sound.createAsync({ uri: localUri }, { shouldPlay: true });
      soundRef.current = sound;

      await queueSessionEvent(sessionId, {
        client_event_id: uuidv4(),
        stop_id: stop.id,
        event_type: 'audio_started',
        occurred_at: new Date().toISOString(),
      });

      sound.setOnPlaybackStatusUpdate(async (status) => {
        if (status.isLoaded && status.didJustFinish) {
          await queueSessionEvent(sessionId, {
            client_event_id: uuidv4(),
            stop_id: stop.id,
            event_type: 'audio_finished',
            occurred_at: new Date().toISOString(),
          });
          await flushQueuedEvents();
        }
      });
    } catch {
      // Audio playback failing shouldn't block the walk — the arrived event
      // is already queued, so progress still advances.
    }
  }

  async function flushQueuedEvents() {
    const queued = await getQueuedEvents(sessionId);
    if (queued.length === 0) return;
    try {
      await sessionsApi.submitEventsBatch(sessionId, queued);
      await clearQueuedEvents(sessionId);
    } catch {
      // Stays queued locally — next successful flush (or app foreground)
      // will retry. client_event_id makes this safe to resend.
    }
  }

  async function handleCompleteWalk() {
    setCompleting(true);
    try {
      await flushQueuedEvents();
      await sessionsApi.complete(sessionId);
      navigation.replace('WalkComplete', { tourId, sessionId });
    } catch {
      Alert.alert(
        'Almost there',
        "All stops are visited but we couldn't confirm completion with the server yet. " +
          "We'll keep retrying — you can also try again from here.",
        [{ text: 'Retry', onPress: handleCompleteWalk }]
      );
    } finally {
      setCompleting(false);
    }
  }

  if (!tour) return null;

  return (
    <ScreenContainer>
      <Text style={styles.title}>{tour.tourPackage.name}</Text>
      <Text style={styles.subtitle}>
        {visitedStopIds.size} of {tour.tourPackage.stops.length} stops visited
      </Text>

      {activeStop && (
        <View style={styles.activeCard}>
          <Text style={styles.activeLabel}>Now playing</Text>
          <Text style={styles.activeStopName}>{activeStop.name}</Text>
          {activeStop.narrative_text && <Text style={styles.activeText}>{activeStop.narrative_text}</Text>}
        </View>
      )}

      {nearestDistance !== null && visitedStopIds.size < tour.tourPackage.stops.length && (
        <Text style={styles.distanceText}>~{Math.round(nearestDistance)} m to next stop</Text>
      )}

      <FlatList
        data={tour.tourPackage.stops}
        keyExtractor={(s) => s.id}
        style={{ marginTop: spacing.lg }}
        renderItem={({ item, index }) => (
          <View style={styles.stopRow}>
            <Text style={[styles.stopIndex, visitedStopIds.has(item.id) && styles.stopDone]}>{index + 1}</Text>
            <Text style={[styles.stopName, visitedStopIds.has(item.id) && styles.stopDone]}>{item.name}</Text>
            {visitedStopIds.has(item.id) && <Text style={styles.checkmark}>\u2713</Text>}
          </View>
        )}
      />

      <PrimaryButton
        title={completing ? 'Finishing up\u2026' : 'End walk early'}
        variant="secondary"
        loading={completing}
        onPress={() =>
          Alert.alert('End walk?', 'Stops you haven\u2019t reached yet will be skipped.', [
            { text: 'Keep walking', style: 'cancel' },
            { text: 'End now', style: 'destructive', onPress: handleCompleteWalk },
          ])
        }
        style={styles.endButton}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.text, fontSize: 20, fontWeight: '800' },
  subtitle: { color: colors.textMuted, fontSize: 14, marginTop: spacing.xs },
  activeCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  activeLabel: { color: colors.primary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  activeStopName: { color: colors.text, fontSize: 18, fontWeight: '700', marginTop: spacing.xs },
  activeText: { color: colors.textMuted, fontSize: 14, marginTop: spacing.sm, lineHeight: 20 },
  distanceText: { color: colors.textMuted, fontSize: 13, marginTop: spacing.md, textAlign: 'center' },
  stopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  stopIndex: { color: colors.textMuted, width: 20 },
  stopName: { color: colors.text, flex: 1 },
  stopDone: { color: colors.success },
  checkmark: { color: colors.success, fontWeight: '700' },
  endButton: { marginTop: spacing.md },
});
