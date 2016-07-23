# -*- coding: utf-8 -*-

import json
from math import log




class EM:
    def __init__(self, example_to_worker_label, worker_to_example_label, label_set):
        self.example_to_worker_label = example_to_worker_label
        self.worker_to_example_label = worker_to_example_label
        self.label_set = label_set

    def ConfusionMatrix(self, worker_to_example_label, example_to_softlabel):
        worker_to_finallabel_weight = {}
        worker_to_finallabel_workerlabel_weight = {}

        for worker, example_label in worker_to_example_label.items():
            if worker not in worker_to_finallabel_weight:
                worker_to_finallabel_weight[worker] = {}
            if worker not in worker_to_finallabel_workerlabel_weight:
                worker_to_finallabel_workerlabel_weight[worker] = {}
            for example, workerlabel in example_label:
                softlabel = example_to_softlabel[example]
                for finallabel, weight in softlabel.items():
                    worker_to_finallabel_weight[worker][finallabel] = worker_to_finallabel_weight[worker].get(finallabel, 0)+weight
                    if finallabel not in worker_to_finallabel_workerlabel_weight[worker]:
                        worker_to_finallabel_workerlabel_weight[worker][finallabel] = {}
                    worker_to_finallabel_workerlabel_weight[worker][finallabel][workerlabel] = worker_to_finallabel_workerlabel_weight[worker][finallabel].get(workerlabel, 0)+weight


        worker_to_confusion_matrix = worker_to_finallabel_workerlabel_weight
        for worker, finallabel_workerlabel_weight in worker_to_finallabel_workerlabel_weight.items():
            for finallabel, workerlabel_weight in finallabel_workerlabel_weight.items():
                if worker_to_finallabel_weight[worker][finallabel] == 0:
                    #approximately no possibility
                    for label in self.label_set:
                        if label==finallabel:
                            worker_to_confusion_matrix[worker][finallabel][label]=0.7
                        else:
                            worker_to_confusion_matrix[worker][finallabel][label]=0.3/(len(self.label_set)-1)
                else:
                    for label in self.label_set:
                        if label in workerlabel_weight:
                            worker_to_confusion_matrix[worker][finallabel][label] = workerlabel_weight[label]*1.0/worker_to_finallabel_weight[worker][finallabel]
                        else:
                            worker_to_confusion_matrix[worker][finallabel][label] = 0.0

        return worker_to_confusion_matrix

    def PriorityProbability(self, example_to_softlabel):
        label_to_priority_probability = {}
        for _, softlabel in example_to_softlabel.items():
            for label, probability in softlabel.items():
                label_to_priority_probability[label] = label_to_priority_probability.get(label,0)+probability
        for label, count in label_to_priority_probability.items():
            label_to_priority_probability[label] = count*1.0/len(example_to_softlabel)
        return label_to_priority_probability


    def ProbabilityMajorityVote(self, example_to_worker_label, label_to_priority_probability, worker_to_confusion_matrix):
        example_to_sortlabel = {}
        for example, worker_label_set in example_to_worker_label.items():
            sortlabel = {}
            total_weight = 0
            # can use worker
            for final_label, priority_probability in label_to_priority_probability.items():
                weight = priority_probability
                for (worker, worker_label) in worker_label_set:
                    weight *= worker_to_confusion_matrix[worker][final_label][worker_label]
                total_weight += weight
                sortlabel[final_label] = weight
            for final_label, weight in sortlabel.items():
                if total_weight == 0:
                    assert weight == 0
                    #approximately less probability
                    sortlabel[final_label]=1.0/len(self.label_set)
                else:
                    sortlabel[final_label] = weight*1.0/total_weight
            example_to_sortlabel[example] = sortlabel
        return example_to_sortlabel


#Pj
    def InitPriorityProbability(self, label_set):
        label_to_priority_probability = {}
        for label in label_set:
            label_to_priority_probability[label] = 1.0/len(label_set)
        return label_to_priority_probability
#Pi
    def InitConfusionMatrix(self, workers, label_set):
        worker_to_confusion_matrix = {}
        for worker in workers:
            if worker not in worker_to_confusion_matrix:
                worker_to_confusion_matrix[worker] = {}
            for label1 in label_set:
                if label1 not in worker_to_confusion_matrix[worker]:
                    worker_to_confusion_matrix[worker][label1] = {}
                for label2 in label_set:
                    if label1 == label2:
                        worker_to_confusion_matrix[worker][label1][label2] = 0.7
                    else:
                        worker_to_confusion_matrix[worker][label1][label2] = 0.3/(len(label_set)-1)
        return worker_to_confusion_matrix

    def ExpectationMaximization(self, iterr = 10):
        example_to_worker_label = self.example_to_worker_label
        worker_to_example_label = self.worker_to_example_label
        label_set = self.label_set

        label_to_priority_probability = self.InitPriorityProbability(label_set)
        worker_to_confusion_matrix = self.InitConfusionMatrix(worker_to_example_label.keys(), label_set)
        while iterr>0:
            example_to_softlabel = self.ProbabilityMajorityVote(example_to_worker_label, label_to_priority_probability, worker_to_confusion_matrix)

            label_to_priority_probability = self.PriorityProbability(example_to_softlabel)
            worker_to_confusion_matrix = self.ConfusionMatrix(worker_to_example_label, example_to_softlabel)

            # compute the likelihood
            #lh=self.computelikelihood(worker_to_confusion_matrix,label_to_priority_probability,example_to_worker_label); # can be omitted
            #print alliter-iterr,':',lh;
            #print alliter-iterr,'\t',lh-prelh
            iterr -= 1

        return example_to_softlabel,label_to_priority_probability,worker_to_confusion_matrix


    def quality_control(self, iterr = 10):
        es, lp, cm = self.ExpectationMaximization(iterr)

        example_to_emlabel = {} # example to final label
        for example, softlabel in es:
            final_label =  max(soft_label.iteritems(), key=operator.itemgetter(1))[0]
            example_to_emlabel[example] = final_label

        return example_to_emlabel


    def computelikelihood(self,w2cm,l2pd,e2wl):
        lh=0;
        for _,wl in e2wl.items():
            temp=0;
            for truelabel,prior in l2pd.items():
                inner=1;
                for workerlabel in wl:
                    worker=workerlabel[0]
                    label=workerlabel[1]
                    inner*=w2cm[worker][truelabel][label]
                temp+=inner*prior
            lh+=log(temp)
        return lh

