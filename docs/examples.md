# JSON Examples

## Metrics Output

```json
{
  "reel_id": "550e8400-e29b-41d4-a716-446655440000",
  "views": 245000,
  "likes": 18500,
  "comments_count": 1200,
  "saves": 3400,
  "shares": 890,
  "reach": 310000,
  "engagement_rate": 9.7551,
  "save_rate": 1.3878,
  "share_rate": 0.3633,
  "comment_rate": 0.4898,
  "virality_score": 0.0124,
  "view_to_follower": 4.0833,
  "growth_rate": null,
  "posting_frequency": null,
  "avg_watch_time_sec": null,
  "content_consistency": null,
  "audience_growth": null,
  "metric_quality": "FULL",
  "is_volatile": false,
  "follower_count": 60000,
  "prev_follower_count": null
}
```

## Content Intelligence Output

```json
{
  "reel_id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "fitness; home workout; 5-minute abs",
  "hook_type": "CURIOSITY",
  "hook_text": "you won't believe this 5-minute abs workout that transformed my body in just 2 weeks",
  "cta": "follow for more quick workout routines and tag a friend who needs to try this",
  "content_format": "TUTORIAL",
  "teaching_style": "Step-by-step",
  "narrative_style": "Direct advice",
  "audience_intent": "Educational",
  "sentiment": "positive",
  "visual_style": "Indoor; Close-up"
}
```

## Creator Profile Output

```json
{
  "account_id": "default",
  "patterns": {
    "best_topics": ["fitness", "nutrition", "workout", "meal prep"],
    "worst_topics": ["technology", "gaming"],
    "best_hook_types": ["CURIOSITY", "PROBLEM_SOLUTION"],
    "best_posting_day": "Wednesday",
    "best_duration_range": "30-60s",
    "best_content_format": "TUTORIAL",
    "audience_interests": ["weight loss", "home gym", "healthy recipes"]
  },
  "competitor_trends": {
    "competitors": [
      {
        "niche": "fitness",
        "winning_format": "TUTORIAL",
        "top_topics": ["HIIT workouts", "protein recipes"],
        "avg_virality": 0.0185
      }
    ],
    "trends": [
      {
        "topic": "12-3-30 workout",
        "hook_pattern": "try this viral workout",
        "content_format": "TUTORIAL",
        "virality_score": 0.045
      }
    ]
  },
  "niche": "fitness"
}
```

## Hybrid Retrieval Results

```json
{
  "query": "quick home workout without equipment",
  "results": [
    {
      "reel_id": "550e8400-e29b-41d4-a716-446655440000",
      "retrieval_score": 0.8923,
      "bm25_score": 0.7654,
      "fused_score": 0.8289,
      "reranker_score": 0.8721,
      "contexts": [
        "no equipment needed for this quick home workout",
        "you can do this 5-minute routine anywhere"
      ],
      "topic": "fitness",
      "hook_text": "no gym? no problem — try this equipment-free home workout",
      "content_format": "TUTORIAL",
      "hook_type": "PROBLEM_SOLUTION",
      "caption": "Quick home workout without equipment #homeworkout #fitness",
      "duration_sec": 45.2
    }
  ],
  "retrieval_confidence": {
    "retrieval_score": 0.8923,
    "reranker_score": 0.8721,
    "coverage_score": 0.8571,
    "combined_score": 0.8746
  }
}
```

## Pipeline Run Output

```json
{
  "pipeline_run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "success",
  "stages": [
    {
      "stage": "enrichment",
      "status": "success",
      "elapsed_sec": 45.23,
      "details": {
        "enriched_count": 10,
        "limit": 10
      }
    },
    {
      "stage": "analytics",
      "status": "success",
      "elapsed_sec": 3.15,
      "details": {
        "analytics_processed": 100,
        "analytics_failed": 0,
        "snapshots_created": 100
      }
    },
    {
      "stage": "intelligence",
      "status": "success",
      "elapsed_sec": 28.67,
      "details": {
        "processed": 100,
        "failed": 0
      }
    },
    {
      "stage": "knowledge",
      "status": "success",
      "elapsed_sec": 5.42,
      "details": {
        "reels_analyzed": 200,
        "profile_updated": true
      }
    }
  ],
  "elapsed_sec": 82.47
}
```

## Agent Chat Response

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": "Based on analysis of 47 reels, your best-performing content fits the TUTORIAL format with CURIOSITY hooks, posted on Wednesdays. Your audience engages most with fitness and nutrition topics, particularly home workout routines under 60 seconds.\n\n**Recommendations:**\n- Continue creating equipment-free home workout tutorials\n- Use curiosity hooks like \"you won't believe this quick routine\"\n- Post on Wednesdays for maximum engagement\n- Explore trending topic \"12-3-30 treadmill workout\" which shows high virality in your niche",
  "citations": [
    {
      "source": "creator_profile",
      "type": "creator_knowledge",
      "summary": "Best topics: [fitness, nutrition, workout, meal prep]"
    },
    {
      "source": "analytics",
      "type": "performance_data",
      "summary": "Avg engagement: 8.24, Reels analyzed: 47"
    },
    {
      "source": "trend_store",
      "type": "trend",
      "summary": "12-3-30 workout"
    }
  ],
  "confidence_score": 0.87,
  "intent": {
    "intent_type": "content_strategy",
    "topic": "fitness",
    "metric": null,
    "time_range": null,
    "comparison_type": null
  },
  "evidence": {
    "source": "llm_reasoner",
    "context_used": [
      "creator_profile",
      "analytics",
      "trend_summary",
      "competitor_insights"
    ]
  },
  "elapsed_sec": 3.45
}
```

## LangGraph State (Mid-Execution)

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_query": "What topics perform best for my audience?",
  "rewritten_query": "best performing content topics audience engagement",
  "intent": {
    "intent_type": "content_strategy",
    "topic": null,
    "metric": "engagement",
    "time_range": null,
    "comparison_type": null
  },
  "metadata_filters": {},
  "retrieval_plan": [
    { "source": "creator_knowledge", "description": "Creator's best topics, hooks, posting patterns" },
    { "source": "analytics", "description": "Performance metrics and engagement data" },
    { "source": "trends", "description": "Trending topics and formats" },
    { "source": "competitor", "description": "Competitor strategies and benchmarks" }
  ],
  "confidence_score": 0.87,
  "ranked_context": {
    "creator_profile": {
      "best_topics": ["fitness", "nutrition", "workout"],
      "best_hook_types": ["CURIOSITY", "PROBLEM_SOLUTION"],
      "best_posting_day": "Wednesday",
      "audience_interests": ["weight loss", "home gym"]
    },
    "analytics": {
      "reel_count": 47,
      "avg_engagement_rate": 8.24,
      "avg_virality_score": 0.0156,
      "total_views": 5200000,
      "total_likes": 185000
    },
    "trend_summary": [
      { "topic": "12-3-30 workout", "viralityScore": 0.045 },
      { "topic": "home gym setup", "viralityScore": 0.032 }
    ],
    "source_count": 3,
    "total_documents": 12,
    "retrieval_confidence": {
      "retrieval_score": 0.8923,
      "reranker_score": 0.8721,
      "coverage_score": 0.8571,
      "combined_score": 0.8746
    }
  },
  "conversation_memory": {
    "session": { "id": "uuid", "userId": "admin", "summary": "interests: fitness | Q: What topics perform best? | A: Based on analysis..." },
    "messages": [
      { "id": "uuid", "role": "user", "content": "What topics perform best for my audience?", "createdAt": "..." },
      { "id": "uuid", "role": "assistant", "content": "Based on analysis of 47 reels...", "citations": [...], "createdAt": "..." }
    ],
    "message_count": 2,
    "preferences": { "topic": "fitness" },
    "summary": "interests: fitness | Q: What topics perform best? | A: Based on analysis..."
  }
}
```

## Transcription Output (Whisper)

```json
{
  "transcript": "You won't believe this quick home workout that I've been doing for the past two weeks. No equipment needed, just ten minutes of your time. First, we start with jumping jacks for thirty seconds...",
  "transcriptJson": [
    {
      "start": 0.5,
      "end": 5.2,
      "text": "You won't believe this quick home workout that I've been doing for the past two weeks.",
      "words": [
        {"start": 0.5, "end": 0.8, "text": "You", "probability": 0.98},
        {"start": 0.8, "end": 1.1, "text": "won't", "probability": 0.99},
        {"start": 1.1, "end": 1.4, "text": "believe", "probability": 0.97}
      ]
    }
  ]
}
```

## Modality Decision Output

```json
{
  "reel_id": "550e8400-e29b-41d4-a716-446655440000",
  "transcript": "...",
  "text_overlays": ["Swipe up for free guide", "5-minute abs routine"],
  "visual_features": {
    "embedding": [0.0123, -0.0456, ..., 0.0789],
    "visual_topics": ["fitness and workout", "indoor setting", "person talking"],
    "visual_summary": "fitness and workout; indoor setting; person talking"
  },
  "modality_decision": {
    "run_transcription": true,
    "run_ocr": true,
    "run_clip": true,
    "scores": {
      "speech_score": 0.82,
      "text_score": 0.45,
      "visual_change_score": 0.12
    }
  },
  "content_intelligence": { "topic": "fitness; home workout", "hook_type": "CURIOSITY", ... },
  "metrics": null
}
```
