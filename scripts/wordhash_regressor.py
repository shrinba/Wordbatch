import os
import re
import json
import pickle as pkl
import gzip
from sklearn.linear_model import *
import scipy.sparse as ssp
import wordbatch
from threading import Thread

non_alphanums = re.compile(u'[\W]')
nums_re= re.compile("\W*[0-9]+\W*")
triples_re= re.compile(ur"(\w)\1{2,}")
trash_re= [re.compile("<[^>]*>"), re.compile("[^a-z0-9' -]+"), re.compile(" [.0-9'-]+ "), re.compile("[-']{2,}"),
           re.compile(" '"),re.compile("  +")]
from nltk.stem.porter import PorterStemmer
stemmer= PorterStemmer()
def normalize_text(text):
    text= text.lower()
    text= nums_re.sub(" NUM ", text)
    text= " ".join([word for word in non_alphanums.sub(" ",text).split() if len(word)>1])
    return text

class WordhashRegressor(object):
    def __init__(self, pickle_model="", datadir=None):
        self.wordbatch= wordbatch.WordBatch(normalize_text,
                                             extractors=[(wordbatch.WordHash, {"decode_error":'ignore', "n_features":2 ** 25,
                                             "non_negative":False, "ngram_range":(1,2), "norm":'l2'})])
        self.clf= Ridge(alpha=1.0, random_state=0)
        if datadir==None:  (self.wordbatch, self.clf)= pkl.load(gzip.open(pickle_model, u'rb'))
        else: self.train(datadir, pickle_model)

    class ThreadWithReturnValue(Thread):
        def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, Verbose=None):
            Thread.__init__(self, group, target, name, args, kwargs, Verbose)
            self._return = None

        def run(self):
            if self._Thread__target is not None:
                self._return = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)

        def join(self):
            Thread.join(self)
            return self._return

    def train(self, datadir, pickle_model=""):
        texts= []
        labels= []
        training_data= os.listdir(datadir)
        rcount= 0
        texts2= []
        batchsize= 100000

        t = None
        for jsonfile in training_data:
            with open(datadir + "/" + jsonfile, u'r') as inputfile:
                for line in inputfile:
                    # if rcount > 1000000: break
                    try:  line = json.loads(line.strip())
                    except:  continue
                    for review in line["Reviews"]:
                        rcount+= 1
                        if rcount % 100000 == 0:  print rcount
                        if rcount % 9 != 0: continue
                        if "Overall" not in review["Ratings"]: continue
                        texts.append(review["Content"])
                        labels.append((float(review["Ratings"]["Overall"]) - 3) * 0.5)
                        if len(texts) % batchsize == 0:
                            if t != None:  texts2.append(t.join())
                            t= self.ThreadWithReturnValue(target=self.wordbatch.transform, args=(texts,))
                            t.start()
                            texts= []
        texts2.append(t.join())
        texts2.append(self.wordbatch.transform(texts))
        del (texts)
        if len(texts2) == 1:  texts= texts2[0]
        else:  texts= ssp.vstack(texts2)

        self.wordbatch.dictionary_freeze = True

        self.clf.fit(texts, labels)
        if pickle_model != "":
            with gzip.open(pickle_model, u'wb') as model_file:
                pkl.dump((self.wordbatch, self.clf), model_file, protocol=2)

    def predict(self, texts):
        counts= self.wordbatch.transform(texts)
        return self.clf.predict(counts)