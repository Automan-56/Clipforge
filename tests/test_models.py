"""Tests unitaires pour les modèles Pydantic."""

from datetime import datetime

import pytest

from clipforge.models import (
    ClipCandidate,
    CropKeyframe,
    CropLayout,
    CropPlan,
    ProjectState,
    Segment,
    Sentence,
    StageState,
    StageStatus,
    SubtitleStyle,
    Transcript,
    Word,
)


class TestWord:
    """Tests pour le modèle Word."""

    def test_word_creation(self) -> None:
        word = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        assert word.start == 1.0
        assert word.end == 1.5
        assert word.text == "hello"
        assert word.probability == 0.95

    def test_word_end_after_start(self) -> None:
        with pytest.raises(ValueError, match="end doit être supérieur à start"):
            Word(start=1.5, end=1.0, text="hello", probability=0.95)

    def test_word_json_roundtrip(self) -> None:
        word = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        data = word.model_dump(mode="json")
        word2 = Word.model_validate(data)
        assert word == word2


class TestSegment:
    """Tests pour le modèle Segment."""

    def test_segment_creation(self) -> None:
        word1 = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        word2 = Word(start=1.5, end=2.0, text="world", probability=0.90)
        segment = Segment(id=1, start=1.0, end=2.0, text="hello world", words=[word1, word2])
        assert segment.id == 1
        assert len(segment.words) == 2

    def test_segment_json_roundtrip(self) -> None:
        word = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        segment = Segment(id=1, start=1.0, end=2.0, text="hello", words=[word])
        data = segment.model_dump(mode="json")
        segment2 = Segment.model_validate(data)
        assert segment == segment2


class TestTranscript:
    """Tests pour le modèle Transcript."""

    def test_transcript_creation(self) -> None:
        word1 = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        word2 = Word(start=1.5, end=2.0, text="world", probability=0.90)
        segment = Segment(id=1, start=1.0, end=2.0, text="hello world", words=[word1, word2])
        transcript = Transcript(
            language="fr",
            language_probability=0.98,
            duration=10.0,
            segments=[segment],
        )
        assert transcript.language == "fr"
        assert len(transcript.words) == 2
        assert transcript.full_text == "hello world"

    def test_transcript_words_between(self) -> None:
        word1 = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        word2 = Word(start=2.0, end=2.5, text="world", probability=0.90)
        word3 = Word(start=3.0, end=3.5, text="test", probability=0.85)
        segment = Segment(id=1, start=1.0, end=4.0, text="hello world test", words=[word1, word2, word3])
        transcript = Transcript(
            language="fr",
            language_probability=0.98,
            duration=10.0,
            segments=[segment],
        )
        # Intervalle intersectant word1 et word2
        words = transcript.words_between(1.2, 2.3)
        assert len(words) == 2
        assert words[0].text == "hello"
        assert words[1].text == "world"

    def test_transcript_json_roundtrip(self) -> None:
        word = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        segment = Segment(id=1, start=1.0, end=2.0, text="hello", words=[word])
        transcript = Transcript(
            language="fr",
            language_probability=0.98,
            duration=10.0,
            segments=[segment],
        )
        data = transcript.model_dump(mode="json")
        transcript2 = Transcript.model_validate(data)
        assert transcript == transcript2


class TestSentence:
    """Tests pour le modèle Sentence."""

    def test_sentence_creation(self) -> None:
        first_word = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        last_word = Word(start=1.5, end=2.0, text="world", probability=0.90)
        sentence = Sentence(
            id=1,
            start=1.0,
            end=2.0,
            text="hello world",
            first_word=first_word,
            last_word=last_word,
        )
        assert sentence.id == 1
        assert sentence.text == "hello world"

    def test_sentence_json_roundtrip(self) -> None:
        first_word = Word(start=1.0, end=1.5, text="hello", probability=0.95)
        last_word = Word(start=1.5, end=2.0, text="world", probability=0.90)
        sentence = Sentence(
            id=1,
            start=1.0,
            end=2.0,
            text="hello world",
            first_word=first_word,
            last_word=last_word,
        )
        data = sentence.model_dump(mode="json")
        sentence2 = Sentence.model_validate(data)
        assert sentence == sentence2


class TestClipCandidate:
    """Tests pour le modèle ClipCandidate."""

    def test_clip_candidate_creation(self) -> None:
        clip = ClipCandidate(
            id=1,
            start=10.0,
            end=30.0,
            start_sentence_id=1,
            end_sentence_id=5,
            title="Test Clip",
            hook="This is a hook",
            summary="Test summary",
            keywords=["test", "clip"],
            llm_score=80.0,
            heuristic_score=75.0,
            final_score=77.5,
            reasons=["Good engagement"],
        )
        assert clip.id == 1
        assert clip.final_score == 77.5
        assert len(clip.keywords) == 2

    def test_clip_candidate_json_roundtrip(self) -> None:
        clip = ClipCandidate(
            id=1,
            start=10.0,
            end=30.0,
            start_sentence_id=1,
            end_sentence_id=5,
            title="Test Clip",
            hook="This is a hook",
            summary="Test summary",
        )
        data = clip.model_dump(mode="json")
        clip2 = ClipCandidate.model_validate(data)
        assert clip == clip2


class TestCropKeyframe:
    """Tests pour le modèle CropKeyframe."""

    def test_crop_keyframe_creation(self) -> None:
        keyframe = CropKeyframe(t=1.0, x_center=0.5, face_count=1, confidence=0.95)
        assert keyframe.t == 1.0
        assert keyframe.x_center == 0.5
        assert keyframe.face_count == 1

    def test_crop_keyframe_json_roundtrip(self) -> None:
        keyframe = CropKeyframe(t=1.0, x_center=0.5, face_count=1, confidence=0.95)
        data = keyframe.model_dump(mode="json")
        keyframe2 = CropKeyframe.model_validate(data)
        assert keyframe == keyframe2


class TestCropPlan:
    """Tests pour le modèle CropPlan."""

    def test_crop_plan_creation(self) -> None:
        keyframe = CropKeyframe(t=1.0, x_center=0.5, face_count=1, confidence=0.95)
        plan = CropPlan(
            clip_id=1,
            layout=CropLayout.CROP,
            src_w=1920,
            src_h=1080,
            crop_w=1080,
            keyframes=[keyframe],
        )
        assert plan.clip_id == 1
        assert plan.layout == CropLayout.CROP
        assert len(plan.keyframes) == 1

    def test_crop_plan_json_roundtrip(self) -> None:
        keyframe = CropKeyframe(t=1.0, x_center=0.5, face_count=1, confidence=0.95)
        plan = CropPlan(
            clip_id=1,
            layout=CropLayout.CROP,
            src_w=1920,
            src_h=1080,
            crop_w=1080,
            keyframes=[keyframe],
        )
        data = plan.model_dump(mode="json")
        plan2 = CropPlan.model_validate(data)
        assert plan == plan2


class TestSubtitleStyle:
    """Tests pour le modèle SubtitleStyle."""

    def test_subtitle_style_creation(self) -> None:
        style = SubtitleStyle(
            font="Arial",
            size=48,
            primary_color="#FFFFFF",
            uppercase=True,
        )
        assert style.font == "Arial"
        assert style.uppercase is True

    def test_subtitle_style_json_roundtrip(self) -> None:
        style = SubtitleStyle(font="Arial", size=48)
        data = style.model_dump(mode="json")
        style2 = SubtitleStyle.model_validate(data)
        assert style == style2


class TestStageStatus:
    """Tests pour le modèle StageStatus."""

    def test_stage_status_creation(self) -> None:
        status = StageStatus(
            state=StageState.RUNNING,
            started_at=datetime(2024, 1, 1, 12, 0),
        )
        assert status.state == StageState.RUNNING
        assert status.started_at is not None

    def test_stage_status_json_roundtrip(self) -> None:
        status = StageStatus(state=StageState.DONE)
        data = status.model_dump(mode="json")
        status2 = StageStatus.model_validate(data)
        assert status == status2


class TestProjectState:
    """Tests pour le modèle ProjectState."""

    def test_project_state_creation(self) -> None:
        state = ProjectState(
            id="test-id",
            source="test.mp4",
            title="Test Project",
            duration=60.0,
        )
        assert state.id == "test-id"
        assert state.source == "test.mp4"
        assert len(state.stages) == 0

    def test_project_state_json_roundtrip(self) -> None:
        state = ProjectState(
            id="test-id",
            source="test.mp4",
            title="Test Project",
            duration=60.0,
        )
        data = state.model_dump(mode="json")
        state2 = ProjectState.model_validate(data)
        assert state == state2
