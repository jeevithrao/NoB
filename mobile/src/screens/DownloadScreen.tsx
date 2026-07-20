import React, { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { Directory, File, Paths } from 'expo-file-system';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import { toursApi, purchasesApi } from '../api/endpoints';
import { saveDownloadedTour, getDownloadedTour } from '../api/offlineStorage';
import { useAuth } from '../context/AuthContext';
import { ApiRequestError } from '../api/client';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<AppStackParamList, 'Download'>;

type Phase = 'checking' | 'ready_to_download' | 'downloading' | 'done' | 'error';

export function DownloadScreen({ route, navigation }: Props) {
  const { tourId } = route.params;
  const { deviceId } = useAuth();
  const [phase, setPhase] = useState<Phase>('checking');
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    (async () => {
      const existing = await getDownloadedTour(tourId);
      setPhase(existing ? 'done' : 'ready_to_download');
    })();
  }, [tourId]);

  async function handleDownload() {
    setPhase('downloading');
    setProgress(0);
    try {
      const tourDetail = await toursApi.get(tourId);

      if (!tourDetail.is_free && tourDetail.purchase_id) {
        try {
          await purchasesApi.bindDevice(tourDetail.purchase_id, deviceId);
        } catch (err) {
          if (err instanceof ApiRequestError && err.code === 'BOUND_TO_OTHER_DEVICE') {
            setErrorMessage(err.message);
            setPhase('error');
            return;
          }
          throw err;
        }
      }

      const pkg = await toursApi.getPackage(tourId);
      const audioLocalPaths: Record<string, string> = {};
      const tourDir = new Directory(Paths.document, 'tours', tourId);
      tourDir.create({ intermediates: true, idempotent: true });

      for (let i = 0; i < pkg.stops.length; i++) {
        const stop = pkg.stops[i];
        try {
          const downloadedFile = await File.downloadFileAsync(stop.audio_url, tourDir, { idempotent: true });
          audioLocalPaths[stop.id] = downloadedFile.uri;
        } catch {
          // Audio files aren't actually hosted in this skeleton yet (seed
          // data references filenames, not uploaded files) — fall back to
          // the remote URL so playback still works once real audio exists,
          // instead of failing the whole download.
          audioLocalPaths[stop.id] = stop.audio_url;
        }
        setProgress((i + 1) / pkg.stops.length);
      }

      await saveDownloadedTour(tourId, {
        tourPackage: pkg,
        downloadedAt: new Date().toISOString(),
        audioLocalPaths,
      });

      setPhase('done');
    } catch (err) {
      const message =
        err instanceof ApiRequestError
          ? err.code === 'BOUND_TO_OTHER_DEVICE'
            ? err.message
            : err.message
          : 'Download failed. Check your connection and try again.';
      setErrorMessage(message);
      setPhase('error');
    }
  }

  return (
    <ScreenContainer style={styles.center}>
      {phase === 'checking' && <Text style={styles.text}>Checking\u2026</Text>}

      {phase === 'ready_to_download' && (
        <>
          <Text style={styles.title}>Download for offline playback</Text>
          <Text style={styles.text}>
            The whole walk works without signal once downloaded \u2014 stops, narration, and GPS
            triggers all run locally.
          </Text>
          <PrimaryButton title="Download now" onPress={handleDownload} style={styles.button} />
        </>
      )}

      {phase === 'downloading' && (
        <>
          <Text style={styles.title}>Downloading\u2026</Text>
          <Text style={styles.text}>{Math.round(progress * 100)}%</Text>
        </>
      )}

      {phase === 'done' && (
        <>
          <Text style={styles.title}>Ready to walk</Text>
          <PrimaryButton
            title="Head to the starting point"
            onPress={() => navigation.replace('RouteToStart', { tourId })}
            style={styles.button}
          />
        </>
      )}

      {phase === 'error' && (
        <>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.text}>{errorMessage}</Text>
          <PrimaryButton title="Try again" onPress={handleDownload} style={styles.button} />
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  center: { justifyContent: 'center', alignItems: 'center' },
  title: { color: colors.text, fontSize: 20, fontWeight: '800', textAlign: 'center', marginBottom: spacing.sm },
  text: { color: colors.textMuted, fontSize: 14, textAlign: 'center', marginBottom: spacing.lg },
  button: { alignSelf: 'stretch' },
});
