import React, { useState } from 'react';
import { Alert, StyleSheet, Text, TextInput } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import { toursApi } from '../api/endpoints';
import { ApiRequestError } from '../api/client';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<AppStackParamList, 'WalkComplete'>;

export function WalkCompleteScreen({ route, navigation }: Props) {
  const { tourId } = route.params;
  const [comment, setComment] = useState('');
  const [posting, setPosting] = useState(false);
  const [posted, setPosted] = useState(false);

  async function handlePostComment() {
    if (!comment.trim()) return;
    setPosting(true);
    try {
      await toursApi.addComment(tourId, comment.trim());
      setPosted(true);
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : 'Could not post your comment.';
      Alert.alert("Couldn't post", message);
    } finally {
      setPosting(false);
    }
  }

  return (
    <ScreenContainer style={styles.center}>
      <Text style={styles.emoji}>\ud83c\udf89</Text>
      <Text style={styles.title}>Walk complete</Text>
      <Text style={styles.subtitle}>
        This tour's playback is now used up \u2014 you can still revisit your notes, but a fresh
        purchase is needed to walk it again.
      </Text>

      {!posted ? (
        <>
          <TextInput
            style={styles.input}
            placeholder="How was the walk?"
            placeholderTextColor={colors.textMuted}
            value={comment}
            onChangeText={setComment}
            multiline
          />
          <PrimaryButton title="Post comment" onPress={handlePostComment} loading={posting} style={styles.button} />
        </>
      ) : (
        <Text style={styles.posted}>Thanks for sharing!</Text>
      )}

      <PrimaryButton
        title="Back to tours"
        variant="secondary"
        onPress={() => navigation.popToTop()}
        style={styles.button}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  center: { justifyContent: 'center', alignItems: 'center' },
  emoji: { fontSize: 48, marginBottom: spacing.md },
  title: { color: colors.text, fontSize: 24, fontWeight: '800', textAlign: 'center' },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: 'center',
    marginTop: spacing.sm,
    marginBottom: spacing.xl,
  },
  input: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    color: colors.text,
    borderRadius: 12,
    padding: spacing.md,
    minHeight: 80,
    textAlignVertical: 'top',
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  posted: { color: colors.success, fontSize: 15, marginBottom: spacing.md },
  button: { alignSelf: 'stretch', marginTop: spacing.sm },
});
