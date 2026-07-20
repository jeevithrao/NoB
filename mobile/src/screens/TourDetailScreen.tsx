import React, { useCallback, useState } from 'react';
import { Alert, Image, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import { StatusPill } from '../components/StatusPill';
import { toursApi, purchasesApi, sessionsApi } from '../api/endpoints';
import { ApiRequestError } from '../api/client';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';
import type { CommentOut, TourDetail as TourDetailType } from '../types';

type Props = NativeStackScreenProps<AppStackParamList, 'TourDetail'>;

export function TourDetailScreen({ route, navigation }: Props) {
  const { tourId } = route.params;
  const [tour, setTour] = useState<TourDetailType | null>(null);
  const [comments, setComments] = useState<CommentOut[]>([]);
  const [newComment, setNewComment] = useState('');
  const [ctaLoading, setCtaLoading] = useState(false);
  const [liked, setLiked] = useState(false);

  const load = useCallback(async () => {
    const [detail, tourComments] = await Promise.all([
      toursApi.get(tourId),
      toursApi.listComments(tourId).catch(() => []),
    ]);
    setTour(detail);
    setComments(tourComments);
  }, [tourId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleToggleLike() {
    setLiked((prev) => !prev);
    try {
      const result = liked ? await toursApi.unlike(tourId) : await toursApi.like(tourId);
      setTour((prev) => (prev ? { ...prev, like_count: (result as any).like_count } : prev));
    } catch {
      setLiked((prev) => !prev); // revert optimistic update on failure
    }
  }

  async function handlePrimaryAction() {
    if (!tour) return;
    setCtaLoading(true);
    try {
      if (tour.status === 'not_purchased') {
        await purchasesApi.create(tour.id);
        navigation.navigate('Download', { tourId: tour.id });
      } else if (tour.status === 'purchased') {
        navigation.navigate('Download', { tourId: tour.id });
      } else if (tour.status === 'in_progress') {
        // Resuming — the backend hands back the existing session either way.
        const session = await sessionsApi.createOrResume(tour.id);
        navigation.navigate('ActiveWalk', { tourId: tour.id, sessionId: session.id });
      }
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : 'Something went wrong.';
      Alert.alert('Unable to continue', message);
    } finally {
      setCtaLoading(false);
    }
  }

  async function handleAddComment() {
    if (!newComment.trim()) return;
    try {
      const comment = await toursApi.addComment(tourId, newComment.trim());
      setComments((prev) => [comment, ...prev]);
      setNewComment('');
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : 'Could not post comment.';
      Alert.alert("Couldn't post comment", message);
    }
  }

  if (!tour) return <ScreenContainer><Text style={styles.loading}>Loading\u2026</Text></ScreenContainer>;

  const ctaLabel =
    tour.status === 'not_purchased'
      ? tour.is_free
        ? 'Get this free tour'
        : `Buy for \u20b9${(tour.price_paise / 100).toFixed(0)}`
      : tour.status === 'purchased'
      ? 'Download tour'
      : tour.status === 'in_progress'
      ? 'Continue walk'
      : 'Walk completed';

  return (
    <ScreenContainer style={{ padding: 0 }}>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        {tour.cover_image && <Image source={{ uri: tour.cover_image }} style={styles.hero} />}
        <View style={styles.content}>
          <Text style={styles.title}>{tour.name}</Text>
          <View style={styles.metaRow}>
            <StatusPill status={tour.status} />
            <Text style={styles.metaText}>
              {tour.duration_min} min \u00b7 {tour.distance_km} km \u00b7 {tour.stop_count} stops
            </Text>
          </View>
          <Text style={styles.description}>{tour.description}</Text>

          <PrimaryButton
            title={ctaLabel}
            onPress={handlePrimaryAction}
            loading={ctaLoading}
            disabled={tour.status === 'completed_locked'}
            style={styles.cta}
          />
          <PrimaryButton
            title={liked ? '\u2665 Liked' : '\u2661 Like this tour'}
            variant="secondary"
            onPress={handleToggleLike}
            style={styles.cta}
          />

          <Text style={styles.sectionTitle}>Comments</Text>
          {tour.status === 'completed_locked' ? (
            <View style={styles.commentInputRow}>
              <TextInput
                style={styles.commentInput}
                placeholder="Share how the walk went\u2026"
                placeholderTextColor={colors.textMuted}
                value={newComment}
                onChangeText={setNewComment}
              />
              <PrimaryButton title="Post" onPress={handleAddComment} />
            </View>
          ) : (
            <Text style={styles.metaText}>Finish walking this tour to leave a comment.</Text>
          )}

          {comments.map((c) => (
            <View key={c.id} style={styles.commentRow}>
              <Text style={styles.commentAuthor}>{c.user_name || 'A walker'}</Text>
              <Text style={styles.commentText}>{c.content}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  loading: { color: colors.textMuted, textAlign: 'center', marginTop: spacing.xl },
  hero: { width: '100%', height: 220 },
  content: { padding: spacing.md },
  title: { color: colors.text, fontSize: 24, fontWeight: '800' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  metaText: { color: colors.textMuted, fontSize: 13 },
  description: { color: colors.text, fontSize: 15, lineHeight: 22, marginTop: spacing.md },
  cta: { marginTop: spacing.md },
  sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '700', marginTop: spacing.xl, marginBottom: spacing.sm },
  commentInputRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'center' },
  commentInput: {
    flex: 1,
    backgroundColor: colors.surface,
    color: colors.text,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  commentRow: { marginTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm },
  commentAuthor: { color: colors.primary, fontWeight: '700', fontSize: 13 },
  commentText: { color: colors.text, fontSize: 14, marginTop: 2 },
});
