"""
Copyright (c) 2019 Intel Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import numpy as np

from ..representation import ClassificationAnnotation, ClassificationPrediction
from ..config import NumberField, StringField
from .metric import PerImageEvaluationMetric
from .average_meter import AverageMeter


class ClassificationAccuracy(PerImageEvaluationMetric):
    """
    Class for evaluating accuracy metric of classification models.
    """

    __provider__ = 'accuracy'

    annotation_types = (ClassificationAnnotation, )
    prediction_types = (ClassificationPrediction, )

    @classmethod
    def parameters(cls):
        parameters = super().parameters()
        parameters.update({
            'top_k': NumberField(
                value_type=int, min_value=1, optional=True, default=1,
                description="The number of classes with the highest probability, which will be used to decide "
                            "if prediction is correct."
            )
        })

        return parameters

    def configure(self):
        self.top_k = self.get_value_from_config('top_k')

        def loss(annotation_label, prediction_top_k_labels):
            return int(annotation_label in prediction_top_k_labels)

        self.accuracy = AverageMeter(loss)

    def update(self, annotation, prediction):
        self.accuracy.update(annotation.label, prediction.top_k(self.top_k))

    def evaluate(self, annotations, predictions):
        return self.accuracy.evaluate()

    def reset(self):
        self.accuracy.reset()


class ClassificationAccuracyClasses(PerImageEvaluationMetric):
    """
    Class for evaluating accuracy for each class of classification models.
    """

    __provider__ = 'accuracy_per_class'

    annotation_types = (ClassificationAnnotation, )
    prediction_types = (ClassificationPrediction, )

    @classmethod
    def parameters(cls):
        parameters = super().parameters()
        parameters.update({
            'top_k': NumberField(
                value_type=int, min_value=1, optional=True, default=1,
                description="The number of classes with the highest probability,"
                            " which will be used to decide if prediction is correct."
            ),
            'label_map': StringField(optional=True, default='label_map', description="Label map.")
        })
        return parameters

    def configure(self):
        self.top_k = self.get_value_from_config('top_k')
        label_map = self.get_value_from_config('label_map')
        self.labels = self.dataset.metadata.get(label_map)
        self.meta['names'] = list(self.labels.values())

        def loss(annotation_label, prediction_top_k_labels):
            result = np.zeros_like(list(self.labels.keys()))
            if annotation_label in prediction_top_k_labels:
                result[annotation_label] = 1

            return result

        def counter(annotation_label):
            result = np.zeros_like(list(self.labels.keys()))
            result[annotation_label] = 1
            return result

        self.accuracy = AverageMeter(loss, counter)

    def update(self, annotation, prediction):
        self.accuracy.update(annotation.label, prediction.top_k(self.top_k))

    def evaluate(self, annotations, predictions):
        return self.accuracy.evaluate()

    def reset(self):
        self.accuracy.reset()


class AverageProbMeter(AverageMeter):
    def __init__(self):
        def loss(annotation_label, prediction_scores):
            return prediction_scores
        super().__init__(loss=loss)


class ClipAccuracy(PerImageEvaluationMetric):
    __provider__ = 'clip_accuracy'

    annotation_types = (ClassificationAnnotation, )
    prediction_types = (ClassificationPrediction, )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clip_accuracy = AverageMeter()
        self.video_accuracy = AverageMeter()
        self.video_avg_prob = AverageProbMeter()
        self.previous_video_id = None
        self.previous_video_label = None

    def update(self, annotation, prediction):
        video_id = annotation.identifier.video

        if self.previous_video_id is not None and video_id != self.previous_video_id:
            video_top_label = np.argmax(self.video_avg_prob.evaluate())
            self.video_accuracy.update(video_top_label, self.previous_video_label)
            self.video_avg_prob = AverageProbMeter()

        self.video_avg_prob.update(annotation.label, prediction.scores)

        self.clip_accuracy.update(annotation.label, prediction.label)

        self.previous_video_id = video_id
        self.previous_video_label = annotation.label

    def evaluate(self, annotations, predictions):
        self.meta['names'] = ['clip_accuracy', 'video_accuracy']
        return [self.clip_accuracy.evaluate(), self.video_accuracy.evaluate()]

    def reset(self):
        self.clip_accuracy.reset()
        self.video_accuracy.reset()
        self.video_avg_prob.reset()
