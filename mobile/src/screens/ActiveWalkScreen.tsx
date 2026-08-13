import React, { useEffect, useRef, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import * as Location from 'expo-location';
import { createAudioPlayer, setAudioModeAsync } from 'expo-audio';
import type { AudioPlayer } from 'expo-audio';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import {
  getDownloadedTour,
  queueSessionEvent,
  getQueuedEvents,
  clearQueuedEvents,
} from '../api/offlineStorage';
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

  const playerRef = useRef<AudioPlayer | null>(null);
  const locationSubscription = useRef<Location.LocationSubscription | null>(null);
  const visitedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const downloaded = await getDownloadedTour(tourId);
      if (!downloaded) return;
      setTour(downloaded);

      await setAudioModeAsync({
        playsInSilentModeIOS: true,
        staysActiveInBackground: true,
      });

      locationSubscription.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.High, timeInterval: 3000, distanceInterval: 5 },
        (position) => {
          if (cancelled) return;
          handlePositionUpdate(
            downloaded,
            position.coords.latitude,
            position.coords.longitude
          );
        }
      );
    })();

    flushQueuedEvents();

    return () => {
      cancelled = true;
      locationSubscription.current?.remove();
      playerRef.current?.release();
    };
  }, [tourId]);

  async function handlePositionUpdate(
    downloaded: DownloadedTour,
    lat: number,
    lng: number
  ) {
    const nextStop = downloaded.tourPackage.stops.find(
      (s) => !visitedRef.current.has(s.id)
    );
    if (!nextStop) return;

    const distance = distanceMeters(
      lat,
      lng,
      parseFloat(nextStop.lat),
      parseFloat(nextStop.lng)
    );
    setNearestDistance(distance);

    if (distance <= nextStop.trigger_radius_m) {
      await handleArrivedAtStop(downloaded, nextStop);
    }
  }

  async function handleArrivedAtStop(
    downloaded: DownloadedTour,
    stop: StopWithAudio
  ) {
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

    const allVisited = downloaded.tourPackage.stops.every((s) =>
      visitedRef.current.has(s.id)
    );
    if (allVisited) {
      await handleCompleteWalk();
    }
  }

  async function playStopAudio(downloaded: DownloadedTour, stop: StopWithAudio) {
    try {
      playerRef.current?.release();

      const localUri = downloaded.audioLocalPaths[stop.id] || stop.audio_url;
      const player = createAudioPlayer({ uri: localUri });
      playerRef.current = player;
      player.play();

      await queueSessionEvent(sessionId, {
        client_event_id: uuidv4(),
        stop_id: stop.id,
        event_type: 'audio_started',
        occurred_at: new Date().toISOString(),
      });

      player.addListener('playbackStatusUpdate', async (status) => {
        if (status.didJustFinish) {
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
      // Audio failing should not block the walk
    }
  }

  async function flushQueuedEvents() {
    const queued = getQueuedEvents(sessionId);
    if (queued.length === 0) return;
    try {
      await sessionsApi.submitEventsBatch(sessionId, queued);
      clearQueuedEvents(sessionId);
    } catch {
      // stays queued for next flush
    }
  }

  async function handleCompleteWalk() {
    if (completing) return;
    setCompleting(true);
    try {
      await flushQueuedEvents();
      await sessionsApi.complete(sessionId);
      navigation.replace('WalkComplete', { tourId });
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Could not complete walk. Try again.');
      setCompleting(false);
    }
  }

  if (!tour) {
    return (
      <ScreenContainer>
        <Text style={styles.muted}>Loading walk…</Text>
      </ScreenContainer>
    );
  }

  const stops = tour.tourPackage.stops;
  const remainingStops = stops.filter((s) => !visitedStopIds.has(s.id));
  const nextStop = remainingStops[0] ?? null;

  return (
    <ScreenContainer>
      {/* Active stop card */}
      {activeStop && (
        <View style={styles.activeCard}>
          <Text style={styles.activeLabel}>NOW PLAYING</Text>
          <Text style={styles.activeName}>{activeStop.name}</Text>
          {activeStop.narrative_text && (
            <Text style={styles.activeNarrative}>{activeStop.narrative_text}</Text>
          )}
        </View>
      )}

      {/* Distance to next stop */}
      {nextStop && nearestDistance !== null && (
        <View style={styles.distanceRow}>
          <Text style={styles.distanceLabel}>Next stop</Text>
          <Text style={styles.distanceName}>{nextStop.name}</Text>
          <Text style={styles.distanceValue}>
            {nearestDistance < 1000
              ? `${Math.round(nearestDistance)}m away`
              : `${(nearestDistance / 1000).toFixed(1)}km away`}
          </Text>
        </View>
      )}

      {/* Stops list */}
      <FlatList
        data={stops}
        keyExtractor={(s) => s.id}
        style={styles.list}
        renderItem={({ item }) => {
          const visited = visitedStopIds.has(item.id);
          const isActive = activeStop?.id === item.id;
          return (
            <View style={[styles.stopRow, isActive && styles.stopRowActive]}>
              <View
                style={[
                  styles.stopDot,
                  visited && styles.stopDotVisited,
                  isActive && styles.stopDotActive,
                ]}
              />
              <Text style={[styles.stopName, visited && styles.stopNameVisited]}>
                {item.name}
              </Text>
            </View>
          );
        }}
      />

      {/* Complete button — shown after last stop visited */}
      {remainingStops.length === 0 && (
        <PrimaryButton
          label={completing ? 'Saving…' : 'Complete walk'}
          onPress={handleCompleteWalk}
          disabled={completing}
        />
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  muted: { color: colors.textMuted, fontFamily: 'SpaceMono', fontSize: 14 },
  activeCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  activeLabel: {
    color: colors.primary,
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: 'SpaceMono',
    marginBottom: 4,
  },
  activeName: { color: colors.text, fontSize: 18, fontFamily: 'SpaceMono', fontWeight: '600' },
  activeNarrative: { color: colors.textMuted, fontSize: 13, marginTop: 6, lineHeight: 20 },
  distanceRow: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  distanceLabel: { color: colors.textMuted, fontSize: 11, letterSpacing: 1 },
  distanceName: { color: colors.text, fontSize: 15, fontWeight: '600', marginTop: 2 },
  distanceValue: { color: colors.primary, fontSize: 22, fontWeight: '700', marginTop: 4 },
  list: { flex: 1 },
  stopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  stopRowActive: { backgroundColor: colors.surface, borderRadius: 8, paddingHorizontal: 8 },
  stopDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.border,
    marginRight: 12,
  },
  stopDotVisited: { backgroundColor: colors.success },
  stopDotActive: { backgroundColor: colors.primary },
  stopName: { color: colors.textMuted, fontSize: 14 },
  stopNameVisited: { color: colors.text },
});