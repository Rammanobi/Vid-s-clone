from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hiker_ingestion.mapper import (
    is_reel,
    map_account,
    map_comment,
    map_metric,
    map_reel,
    unwrap_clips,
    unwrap_comments,
    unwrap_media_info,
    unwrap_user,
)
from hiker_ingestion.models import MetricQuality


class TestUnwrap:
    def test_unwrap_user(self) -> None:
        response = {"status": "ok", "user": {"pk": 45093317380, "username": "okaashish"}}
        assert unwrap_user(response) == {"pk": 45093317380, "username": "okaashish"}

    def test_unwrap_user_missing(self) -> None:
        assert unwrap_user({"status": "ok"}) == {}

    def test_unwrap_clips_double_nesting(self) -> None:
        response = {
            "response": {
                "items": [
                    {"media": {"pk": "3944679501543145356", "code": "Da-URtaPn-M"}},
                    {"media": {"pk": "3943963598434214932", "code": "Da7xf8rviQU"}},
                ]
            }
        }
        clips = unwrap_clips(response)
        assert len(clips) == 2
        assert clips[0]["pk"] == "3944679501543145356"
        assert clips[1]["code"] == "Da7xf8rviQU"

    def test_unwrap_clips_empty(self) -> None:
        assert unwrap_clips({"response": {"items": []}}) == []
        assert unwrap_clips({}) == []

    def test_unwrap_comments(self) -> None:
        response = {"response": {"comments": [{"pk": "1", "text": "hi"}]}}
        assert unwrap_comments(response) == [{"pk": "1", "text": "hi"}]

    def test_unwrap_media_info(self) -> None:
        response = {"status": "ok", "media_or_ad": {"pk": "1", "play_count": 100}}
        assert unwrap_media_info(response) == {"pk": "1", "play_count": 100}


class TestIsReel:
    def test_clip_video_is_reel(self) -> None:
        assert is_reel({"product_type": "clips", "media_type": 2}) is True

    def test_wrong_media_type_is_not_reel(self) -> None:
        assert is_reel({"product_type": "clips", "media_type": 1}) is False

    def test_wrong_product_type_is_not_reel(self) -> None:
        assert is_reel({"product_type": "feed", "media_type": 2}) is False

    def test_missing_fields_is_not_reel(self) -> None:
        assert is_reel({}) is False


class TestMapAccount:
    def test_full_data(self) -> None:
        user = {
            "pk": 45093317380,
            "username": "okaashish",
            "follower_count": 150165,
            "following_count": 389,
            "media_count": 533,
        }
        result = map_account(user)
        assert result.instagram_id == "45093317380"
        assert result.username == "okaashish"
        assert result.follower_count == 150165
        assert result.following_count == 389
        assert result.posts_count == 533
        assert result.is_competitor is False

    def test_numeric_pk_coerced_to_string(self) -> None:
        # safe_int=true: user pk arrives as a JSON number, not a string.
        result = map_account({"pk": 45093317380, "username": "u"})
        assert result.instagram_id == "45093317380"
        assert isinstance(result.instagram_id, str)

    def test_minimal_data(self) -> None:
        result = map_account({"username": "minimal"})
        assert result.instagram_id == ""
        assert result.username == "minimal"
        assert result.follower_count == 0
        assert result.following_count == 0
        assert result.posts_count == 0

    def test_null_counts(self) -> None:
        user = {"pk": 1, "username": "u", "follower_count": None, "following_count": None}
        result = map_account(user)
        assert result.follower_count == 0
        assert result.following_count == 0

    def test_id_fallback_when_pk_absent(self) -> None:
        result = map_account({"id": "999", "username": "alt"})
        assert result.instagram_id == "999"


class TestMapReel:
    def test_full_data(self) -> None:
        media = {
            "pk": "3944679501543145356",
            "code": "Da-URtaPn-M",
            "video_versions": [
                {"bandwidth": 500000, "url": "https://example.com/low.mp4"},
                {"bandwidth": 1284735, "url": "https://example.com/high.mp4"},
            ],
            "caption": {"text": "Comment \"certificate\" and I'll send you the official links.\n"},
            "video_duration": 39.75,
            "taken_at": 1784462647,
        }
        result = map_reel(media, "account-uuid")
        assert result.account_id == "account-uuid"
        assert result.instagram_reel_id == "3944679501543145356"
        # highest-bandwidth rendition wins, not index 0
        assert result.video_url == "https://example.com/high.mp4"
        assert result.caption == "Comment \"certificate\" and I'll send you the official links.\n"
        assert result.duration_sec == 39.75
        assert result.posted_at == datetime.fromtimestamp(1784462647, tz=timezone.utc).replace(tzinfo=None)

    def test_string_pk_preserved(self) -> None:
        # safe_int=true: 19-digit media pk arrives as a JSON string.
        result = map_reel({"pk": "3944679501543145356"}, "aid")
        assert result.instagram_reel_id == "3944679501543145356"

    def test_caption_object_without_text_key(self) -> None:
        result = map_reel({"pk": "r2", "caption": {"created_at": 123}}, "aid")
        assert result.caption is None

    def test_caption_null(self) -> None:
        result = map_reel({"pk": "r3", "caption": None}, "aid")
        assert result.caption is None

    def test_caption_never_stringified_if_object_has_no_text(self) -> None:
        # Guards against accidentally doing str(caption_obj) as a fallback.
        result = map_reel({"pk": "r4", "caption": {"foo": "bar"}}, "aid")
        assert result.caption is None

    def test_minimal_data_no_video_versions(self) -> None:
        result = map_reel({"pk": "r5"}, "aid")
        assert result.video_url == ""
        assert result.caption is None
        assert result.duration_sec == 0.0
        assert result.posted_at is None

    def test_single_video_version(self) -> None:
        media = {"pk": "r6", "video_versions": [{"bandwidth": 100, "url": "https://x/one.mp4"}]}
        result = map_reel(media, "aid")
        assert result.video_url == "https://x/one.mp4"

    def test_video_version_missing_bandwidth_does_not_crash(self) -> None:
        media = {
            "pk": "r7",
            "video_versions": [
                {"url": "https://x/no-bandwidth.mp4"},
                {"bandwidth": 500, "url": "https://x/has-bandwidth.mp4"},
            ],
        }
        result = map_reel(media, "aid")
        assert result.video_url == "https://x/has-bandwidth.mp4"


class TestMapComment:
    def test_full_data_non_owner(self) -> None:
        raw = {
            "pk": "18209380177352304",  # the COMMENT's own id - must NOT be used as author
            "user": {"pk": 47831239820, "username": "call_me_v_m"},
            "text": "Certificate",
            "created_at": 1784474021,
        }
        result = map_comment(raw, "reel-uuid", creator_id="45093317380")
        assert result.reel_id == "reel-uuid"
        assert result.author_id == "47831239820"
        assert result.text == "Certificate"
        assert result.is_creator is False
        assert result.posted_at == datetime.fromtimestamp(1784474021, tz=timezone.utc).replace(tzinfo=None)

    def test_creator_comment(self) -> None:
        raw = {"pk": "999", "user": {"pk": 45093317380}, "text": "Thanks!"}
        result = map_comment(raw, "rid", creator_id="45093317380")
        assert result.is_creator is True

    def test_comment_pk_is_never_used_as_author(self) -> None:
        # Regression test: an earlier version of this mapper read the
        # comment's own `pk` as the author, so isCreator could never be true
        # even for the account owner's own comments.
        raw = {"pk": "45093317380", "user": {"pk": 999}, "text": "not the owner"}
        result = map_comment(raw, "rid", creator_id="45093317380")
        assert result.author_id == "999"
        assert result.is_creator is False

    def test_user_id_fallback_when_user_object_absent(self) -> None:
        raw = {"pk": "1", "user_id": 47831239820, "text": "hi"}
        result = map_comment(raw, "rid")
        assert result.author_id == "47831239820"

    def test_no_creator_id_provided(self) -> None:
        raw = {"pk": "1", "user": {"pk": 1}, "text": "hi"}
        result = map_comment(raw, "rid", creator_id=None)
        assert result.is_creator is False

    def test_minimal_data(self) -> None:
        result = map_comment({}, "rid")
        assert result.author_id == ""
        assert result.text == ""
        assert result.is_creator is False


class TestMapMetric:
    def test_full_metrics_matches_worked_example(self) -> None:
        # Real values from research-metrics.md / mapper.py's own self-check.
        raw = {
            "play_count": 11875,
            "like_count": 146,
            "comment_count": 122,
            "save_count": 136,
            "reshare_count": 74,
        }
        result = map_metric(raw, "reel-uuid", follower_count=150165)
        assert result.reel_id == "reel-uuid"
        assert result.views == 11875
        assert result.likes == 146
        assert result.comments_count == 122
        assert result.saves == 136
        assert result.shares == 74
        assert result.metric_quality == MetricQuality.FULL
        assert result.engagement_rate == round((146 + 122 + 136 + 74) / 11875 * 100, 4) == 4.0253
        assert result.save_rate == round(136 / 11875 * 100, 4) == 1.1453
        assert result.share_rate == round(74 / 11875 * 100, 4) == 0.6232
        assert result.view_to_follower == round(11875 / 150165 * 100, 4) == 7.9080
        assert result.virality_score == round(4.0253 * 0.5 + 0.6232 * 0.3 + 7.9080 * 0.2, 4) == 3.7812

    def test_play_count_already_equals_ig_plus_fb_so_views_is_unaffected_by_either(
        self,
    ) -> None:
        # research-metrics.md verified play_count == ig_play_count + fb_play_count
        # exactly (e.g. 11875 == 8152 + 3723) on every sampled reel - play_count
        # is the correct single source and the mapper deliberately never reads
        # ig_play_count/fb_play_count itself. This guards that invariant: views
        # must come from play_count regardless of what the (irrelevant, always
        # ignored) component fields say - including when fb_play_count is None
        # (no FB cross-post), which must NOT be treated as zero engagement.
        raw = {
            "play_count": 11875,
            "ig_play_count": 8152,
            "fb_play_count": 3723,
            "like_count": 1,
            "comment_count": 1,
        }
        assert raw["ig_play_count"] + raw["fb_play_count"] == raw["play_count"]
        result = map_metric(raw, "reel-uuid")
        assert result.views == 11875

        raw_no_fb_crosspost = {
            "play_count": 8152,
            "ig_play_count": 8152,
            "fb_play_count": None,
            "like_count": 1,
            "comment_count": 1,
        }
        result_no_fb = map_metric(raw_no_fb_crosspost, "reel-uuid")
        assert result_no_fb.views == 8152  # not 0, not None

    def test_views_sourced_from_play_count_not_view_count(self) -> None:
        # view_count/video_view_count do not exist in any real payload - a
        # regression here would mean someone reintroduced that dead lookup.
        raw = {"play_count": 500, "view_count": 999999, "like_count": 1, "comment_count": 1}
        result = map_metric(raw, "rid")
        assert result.views == 500

    def test_shares_sourced_from_reshare_count_not_share_count(self) -> None:
        raw = {
            "play_count": 1000,
            "like_count": 1,
            "comment_count": 1,
            "reshare_count": 74,
            "share_count": 999999,  # does not exist on the real API; must be ignored
            "media_repost_count": 127,  # a different, smaller metric; must be ignored
        }
        result = map_metric(raw, "rid")
        assert result.shares == 74

    def test_no_reach_field_exists(self) -> None:
        raw = {"play_count": 100, "like_count": 1, "comment_count": 1}
        result = map_metric(raw, "rid")
        assert not hasattr(result, "reach")

    def test_partial_metrics_when_saves_and_shares_missing(self) -> None:
        raw = {"play_count": 1000, "like_count": 50, "comment_count": 5}
        result = map_metric(raw, "rid")
        assert result.saves is None
        assert result.shares is None
        assert result.metric_quality == MetricQuality.PARTIAL

    def test_full_quality_requires_only_core_five_fields(self) -> None:
        # FULL/PARTIAL depends solely on views/likes/commentsCount/saves/shares -
        # reach/impressions are structurally absent and must not affect this.
        raw = {
            "play_count": 100,
            "like_count": 10,
            "comment_count": 2,
            "save_count": 1,
            "reshare_count": 0,
        }
        result = map_metric(raw, "rid")
        assert result.metric_quality == MetricQuality.FULL

    def test_engagement_rate_divides_by_views_not_followers(self) -> None:
        # Regression test: an earlier version of this mapper divided
        # engagement_rate by follower_count, contradicting save_rate/share_rate
        # a few lines below it, which always divided by views.
        raw = {
            "play_count": 1000,
            "like_count": 100,
            "comment_count": 10,
            "save_count": 20,
            "reshare_count": 5,
        }
        result = map_metric(raw, "rid", follower_count=1_000_000)
        expected_er = ((100 + 10 + 20 + 5) / 1000) * 100
        assert result.engagement_rate == round(expected_er, 4)
        assert result.engagement_rate != round((100 + 10 + 20 + 5) / 1_000_000 * 100, 4)

    def test_zero_views_and_zero_followers_guard(self) -> None:
        raw = {"play_count": 0, "like_count": 10, "comment_count": 1}
        result = map_metric(raw, "rid", follower_count=0)
        assert result.engagement_rate == 0.0
        assert result.save_rate == 0.0
        assert result.share_rate == 0.0
        assert result.comment_rate == 0.0
        assert result.view_to_follower == 0.0
        assert result.virality_score == 0.0

    def test_null_numeric_fields_do_not_raise(self) -> None:
        raw = {"play_count": None, "like_count": None, "comment_count": None}
        result = map_metric(raw, "rid")
        assert result.views == 0
        assert result.likes == 0
        assert result.comments_count == 0
        assert result.metric_quality == MetricQuality.PARTIAL

    def test_high_engagement_reel(self) -> None:
        raw = {
            "play_count": 1_000_000,
            "like_count": 500_000,
            "comment_count": 100_000,
            "save_count": 200_000,
            "reshare_count": 150_000,
        }
        result = map_metric(raw, "rid", follower_count=10_000)
        assert result.view_to_follower == round(1_000_000 / 10_000 * 100, 4)
        assert result.virality_score > 0
