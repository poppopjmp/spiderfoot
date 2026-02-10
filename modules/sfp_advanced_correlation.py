# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_advanced_correlation
# Purpose:      Advanced data correlation and entity resolution engine
#
# Author:      Agostino Panico van1sh@van1shland.io
#
# Created:     20/06/2025
# Copyright:   (c) Agostino Panico 2025
# License:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
Advanced Correlation Engine

Provides sophisticated data correlation capabilities including:
- Cross-platform user identity resolution
- Temporal pattern analysis
- Geospatial intelligence correlation
- Behavioral analytics
- Entity relationship mapping
- Multi-source data fusion
"""

import json
import re
import time
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Any
import hashlib
import logging

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class AdvancedCorrelationEngine:
    """Advanced correlation engine for OSINT data analysis."""
    
    def __init__(self) -> None:
        self.entity_graph = defaultdict(set)
        self.temporal_events = []
        self.geo_clusters = defaultdict(list)
        self.behavior_patterns = defaultdict(list)
        self.confidence_scores = {}
        
    def add_entity_relationship(self, entity1: str, entity2: str, relationship_type: str, confidence: float):
        """Add a relationship between two entities."""
        self.entity_graph[entity1].add((entity2, relationship_type, confidence))
        self.entity_graph[entity2].add((entity1, relationship_type, confidence))
        
    def find_connected_entities(self, entity: str, max_depth: int = 3) -> dict[str, Any]:
        """Find all entities connected to a given entity."""
        visited = set()
        queue = [(entity, 0)]
        connections = defaultdict(list)
        
        while queue:
            current_entity, depth = queue.pop(0)
            if current_entity in visited or depth >= max_depth:
                continue
                
            visited.add(current_entity)
            
            for connected_entity, rel_type, confidence in self.entity_graph[current_entity]:
                if connected_entity not in visited:
                    connections[depth].append({
                        'entity': connected_entity,
                        'relationship': rel_type,
                        'confidence': confidence
                    })
                    queue.append((connected_entity, depth + 1))
                    
        return dict(connections)
        
    def analyze_temporal_patterns(self, events: list[dict], time_window_hours: int = 24) -> list[dict]:
        """Analyze temporal patterns in events."""
        patterns = []
        events_by_time = defaultdict(list)
        
        # Group events by time windows
        for event in events:
            if 'timestamp' in event:
                time_bucket = int(event['timestamp'] // (time_window_hours * 3600))
                events_by_time[time_bucket].append(event)
        
        # Identify patterns
        for time_bucket, bucket_events in events_by_time.items():
            if len(bucket_events) > 1:
                pattern = {
                    'time_window': time_bucket * time_window_hours * 3600,
                    'event_count': len(bucket_events),
                    'event_types': Counter(e.get('type', 'unknown') for e in bucket_events),
                    'entities': set(e.get('entity', '') for e in bucket_events),
                    'confidence': min(1.0, len(bucket_events) / 10.0)
                }
                patterns.append(pattern)
                
        return patterns
        
    def cluster_geospatial_data(self, geo_data: list[dict], radius_km: float = 50.0) -> list[dict]:
        """Cluster geospatial data points."""
        clusters = []
        used_points = set()
        
        for i, point1 in enumerate(geo_data):
            if i in used_points:
                continue
                
            cluster = [point1]
            used_points.add(i)
            
            for j, point2 in enumerate(geo_data[i+1:], i+1):
                if j in used_points:
                    continue
                    
                distance = self._calculate_distance(
                    point1.get('lat', 0), point1.get('lng', 0),
                    point2.get('lat', 0), point2.get('lng', 0)
                )
                
                if distance <= radius_km:
                    cluster.append(point2)
                    used_points.add(j)
            
            if len(cluster) > 1:
                clusters.append({
                    'center': self._calculate_centroid(cluster),
                    'points': cluster,
                    'radius': self._calculate_cluster_radius(cluster),
                    'confidence': min(1.0, len(cluster) / 5.0)
                })
                
        return clusters
        
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        import math
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
        
    def _calculate_centroid(self, points: list[dict]) -> dict[str, float]:
        """Calculate centroid of a cluster of points."""
        lats = [p.get('lat', 0) for p in points]
        lngs = [p.get('lng', 0) for p in points]
        
        return {
            'lat': sum(lats) / len(lats),
            'lng': sum(lngs) / len(lngs)
        }
        
    def _calculate_cluster_radius(self, points: list[dict]) -> float:
        """Calculate the radius of a cluster."""
        if len(points) < 2:
            return 0.0
            
        centroid = self._calculate_centroid(points)
        max_distance = 0.0
        
        for point in points:
            distance = self._calculate_distance(
                centroid['lat'], centroid['lng'],
                point.get('lat', 0), point.get('lng', 0)
            )
            max_distance = max(max_distance, distance)
            
        return max_distance


class sfp_advanced_correlation(SpiderFootModernPlugin):
    """Advanced correlation and entity resolution module."""

    meta = {
        'name': "Advanced Correlation Engine",
        'summary': "Performs advanced correlation analysis across all collected data to identify relationships and patterns.",
        'flags': [],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Content Analysis"],
        'dataSource': {
            'website': "N/A",
            'model': "FREE_NOAUTH_UNLIMITED",
            'description': "Internal correlation engine that analyzes relationships between discovered entities."
        }
    }

    opts = {
        'enable_entity_resolution': True,
        'enable_temporal_analysis': True,
        'enable_geospatial_clustering': True,
        'enable_behavioral_analysis': True,
        'correlation_confidence_threshold': 0.7,
        'temporal_window_hours': 24,
        'geo_cluster_radius_km': 50.0,
        'max_entity_depth': 3,
        'min_pattern_strength': 3
    }

    optdescs = {
        'enable_entity_resolution': "Enable cross-platform entity resolution",
        'enable_temporal_analysis': "Enable temporal pattern analysis",
        'enable_geospatial_clustering': "Enable geospatial data clustering",
        'enable_behavioral_analysis': "Enable behavioral pattern analysis",
        'correlation_confidence_threshold': "Minimum confidence score for correlations",
        'temporal_window_hours': "Time window for temporal analysis (hours)",
        'geo_cluster_radius_km': "Radius for geospatial clustering (kilometers)",
        'max_entity_depth': "Maximum depth for entity relationship traversal",
        'min_pattern_strength': "Minimum number of events to form a pattern"
    }

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.correlation_engine = AdvancedCorrelationEngine()
        self.collected_events = []
        self.entity_cache = {}
    def watchedEvents(self):
        return ["*"]

    def producedEvents(self):
        return [
            "ENTITY_RELATIONSHIP",
            "TEMPORAL_PATTERN",
            "GEOSPATIAL_CLUSTER", 
            "BEHAVIORAL_PATTERN",
            "IDENTITY_RESOLUTION",
            "CORRELATION_ANALYSIS"
        ]

    def handleEvent(self, event):
        eventName = event.eventType
        eventData = event.data
        
        # Store event for correlation analysis
        event_record = {
            'type': eventName,
            'data': eventData,
            'module': event.module,
            'timestamp': event.generated,
            'confidence': event.confidence,
            'entity_hash': self._create_entity_hash(eventData)
        }
        
        self.collected_events.append(event_record)
        
        # Perform real-time correlation for high-value events
        if eventName in ['SOCIAL_MEDIA_PROFILE', 'EMAILADDR', 'PHONE_NUMBER', 'HUMAN_NAME']:
            self._perform_realtime_correlation(event_record, event)

    def _create_entity_hash(self, data: str) -> str:
        """Create a hash for entity identification."""
        normalized_data = data.lower().strip()
        return hashlib.md5(normalized_data.encode()).hexdigest()[:12]

    def _perform_realtime_correlation(self, event_record: dict, source_event: SpiderFootEvent):
        """Perform real-time correlation analysis for high-value events."""
        entity_hash = event_record['entity_hash']
        
        # Look for related entities in cache
        related_entities = self._find_related_entities(event_record)
        
        if related_entities:
            correlation_data = {
                'primary_entity': event_record['data'],
                'related_entities': related_entities,
                'correlation_strength': len(related_entities),
                'analysis_timestamp': time.time()
            }
            
            correlation_event = SpiderFootEvent(
                "ENTITY_RELATIONSHIP",
                json.dumps(correlation_data),
                self.__name__,
                source_event
            )
            self.notifyListeners(correlation_event)

    def _find_related_entities(self, event_record: dict) -> list[dict]:
        """Find entities related to the current event."""
        related = []
        current_data = event_record['data'].lower()
        
        for other_event in self.collected_events[-100:]:  # Look at last 100 events
            if other_event['entity_hash'] == event_record['entity_hash']:
                continue
                
            similarity = self._calculate_similarity(current_data, other_event['data'].lower())
            
            if similarity > self.opts['correlation_confidence_threshold']:
                related.append({
                    'entity': other_event['data'],
                    'type': other_event['type'],
                    'similarity': similarity,
                    'module': other_event['module']
                })
                
        return related

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings."""
        # Simple similarity calculation based on common substrings
        if not str1 or not str2:
            return 0.0
            
        # Check for exact match
        if str1 == str2:
            return 1.0
            
        # Check for substring matches
        shorter, longer = (str1, str2) if len(str1) < len(str2) else (str2, str1)
        
        if shorter in longer:
            return len(shorter) / len(longer)
            
        # Check for common words/tokens
        tokens1 = set(re.findall(r'\w+', str1))
        tokens2 = set(re.findall(r'\w+', str2))
        
        if not tokens1 or not tokens2:
            return 0.0
            
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0

    def scanFinished(self):
        """Perform comprehensive correlation analysis when scan finishes."""
        if not self.collected_events:
            return
            
        self.info(f"Starting comprehensive correlation analysis of {len(self.collected_events)} events")
        
        # Perform temporal analysis
        if self.opts['enable_temporal_analysis']:
            self._analyze_temporal_patterns()
            
        # Perform geospatial clustering
        if self.opts['enable_geospatial_clustering']:
            self._analyze_geospatial_patterns()
            
        # Perform entity resolution
        if self.opts['enable_entity_resolution']:
            self._perform_entity_resolution()
            
        # Perform behavioral analysis
        if self.opts['enable_behavioral_analysis']:
            self._analyze_behavioral_patterns()

    def _analyze_temporal_patterns(self):
        """Analyze temporal patterns in collected events."""
        patterns = self.correlation_engine.analyze_temporal_patterns(
            self.collected_events, 
            self.opts['temporal_window_hours']
        )
        
        for pattern in patterns:
            if pattern['confidence'] >= self.opts['correlation_confidence_threshold']:
                pattern_event = SpiderFootEvent(
                    "TEMPORAL_PATTERN",
                    json.dumps(pattern),
                    self.__name__,
                    None
                )
                self.notifyListeners(pattern_event)

    def _analyze_geospatial_patterns(self):
        """Analyze geospatial clustering in collected events."""
        geo_events = [e for e in self.collected_events if e['type'] == 'GEOINFO']
        
        if len(geo_events) < 2:
            return
            
        geo_data = []
        for event in geo_events:
            try:
                # Try to parse geo data
                if ',' in event['data']:
                    parts = event['data'].split(',')
                    if len(parts) >= 2:
                        lat, lng = float(parts[0].strip()), float(parts[1].strip())
                        geo_data.append({'lat': lat, 'lng': lng, 'event': event})
            except (ValueError, IndexError):
                continue
                
        clusters = self.correlation_engine.cluster_geospatial_data(
            geo_data, 
            self.opts['geo_cluster_radius_km']
        )
        
        for cluster in clusters:
            if cluster['confidence'] >= self.opts['correlation_confidence_threshold']:
                cluster_event = SpiderFootEvent(
                    "GEOSPATIAL_CLUSTER",
                    json.dumps(cluster),
                    self.__name__,
                    None
                )
                self.notifyListeners(cluster_event)

    def _perform_entity_resolution(self):
        """Perform comprehensive entity resolution across all collected data."""
        entity_groups = defaultdict(list)
        
        # Group similar entities
        for event in self.collected_events:
            if event['type'] in ['HUMAN_NAME', 'EMAILADDR', 'USERNAME', 'SOCIAL_MEDIA_PROFILE']:
                similar_found = False
                
                for group_key, group_events in entity_groups.items():
                    if any(self._calculate_similarity(event['data'], e['data']) > 0.8 for e in group_events):
                        entity_groups[group_key].append(event)
                        similar_found = True
                        break
                        
                if not similar_found:
                    entity_groups[event['entity_hash']].append(event)
        
        # Generate identity resolution events for groups with multiple entities
        for group_key, group_events in entity_groups.items():
            if len(group_events) > 1:
                resolution_data = {
                    'resolved_identity': group_key,
                    'entities': [{'data': e['data'], 'type': e['type'], 'module': e['module']} for e in group_events],
                    'confidence': min(1.0, len(group_events) / 5.0),
                    'resolution_timestamp': time.time()
                }
                
                resolution_event = SpiderFootEvent(
                    "IDENTITY_RESOLUTION",
                    json.dumps(resolution_data),
                    self.__name__,
                    None
                )
                self.notifyListeners(resolution_event)

    def _analyze_behavioral_patterns(self):
        """Analyze behavioral patterns in user activities."""
        user_activities = defaultdict(list)
        
        # Group activities by user/entity
        for event in self.collected_events:
            if event['type'] in ['SOCIAL_MEDIA_PROFILE', 'SOCIAL_MEDIA_CONTENT', 'USERNAME']:
                user_key = event['entity_hash']
                user_activities[user_key].append(event)
        
        # Analyze patterns for each user
        for user_key, activities in user_activities.items():
            if len(activities) >= self.opts['min_pattern_strength']:
                pattern_analysis = self._analyze_user_behavior(activities)
                
                if pattern_analysis['confidence'] >= self.opts['correlation_confidence_threshold']:
                    behavior_event = SpiderFootEvent(
                        "BEHAVIORAL_PATTERN",
                        json.dumps(pattern_analysis),
                        self.__name__,
                        None
                    )
                    self.notifyListeners(behavior_event)

    def _analyze_user_behavior(self, activities: list[Dict]) -> dict[str, Any]:
        """Analyze behavior patterns for a specific user."""
        activity_times = [a['timestamp'] for a in activities]
        activity_types = [a['type'] for a in activities]
        
        # Calculate time-based patterns
        time_intervals = []
        for i in range(1, len(activity_times)):
            interval = activity_times[i] - activity_times[i-1]
            time_intervals.append(interval)
        
        avg_interval = sum(time_intervals) / len(time_intervals) if time_intervals else 0
        
        # Calculate activity type distribution
        type_distribution = Counter(activity_types)
        
        return {
            'user_hash': activities[0]['entity_hash'],
            'activity_count': len(activities),
            'time_span': max(activity_times) - min(activity_times) if activity_times else 0,
            'average_interval': avg_interval,
            'activity_types': dict(type_distribution),
            'confidence': min(1.0, len(activities) / 10.0),
            'analysis_timestamp': time.time()
        }
