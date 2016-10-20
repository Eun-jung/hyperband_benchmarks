import time
import numpy
import functools
import pickle
import os
import sys,getopt
from robo.fmin import fabolas_fmin


class Logger(object):
    def __init__(self,dir):
        self.terminal = sys.stdout
        self.log = open(dir+"/hyperband_run.log", "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

class fabolas_search:
    def __init__(self,params,model,units,budget,runtime,dir,min_units,max_units):
        self.results=[]
        self.params=params
        self.model=model
        self.units=units
        self.budget=budget
        self.runtime=runtime
        self.dir=dir
        self.min_units=min_units
        self.max_units=max_units
        self.hps=params.keys()
        self.arms=[]
    def get_hp_ranges(self):
        X_min=[]
        X_max=[]
        for h in self.hps:
            X_min.append(self.params[h].get_min())
            X_max.append(self.params[h].get_max())
        X_min.append(numpy.log(self.min_units))
        X_max.append(numpy.log(self.max_units))
        X_min=numpy.array(X_min)
        X_max=numpy.array(X_max)
        return X_min, X_max


    def objective_function(self,x,s,calc_test_error=False):
        try:
            start_time=time.time()
            n_units=int(numpy.exp(s))
            self.budget=self.budget-n_units
            if self.budget<0:
                pickle.dump(self.results,open(self.dir+'/results.pkl','wb'))
                raise Exception
            arm=None
            #transform params
            for i in range(len(self.hps)):
                hp=self.hps[i]
                x[0,i]=self.params[hp].get_transformed_param(x[0,i])
            if calc_test_error:
                for a in self.arms:
                    if numpy.isclose(a[self.hps[0]],x[0,0],10.0**(-6)):
                        arm=a
                    n_units=self.max_units
            else:
                #get an arm to set up directory structure and fill in default params
                arm=self.model.generate_arms(1,self.dir, self.params)[0]
                #replace random values with values in x vector
                for i in range(len(self.hps)):
                    hp=self.hps[i]
                    arm[hp]=x[0,i]
                self.arms.append(arm)
            train_loss,val_acc, test_acc=self.model.run_solver(self.units, n_units, arm)
            duration=time.time()-start_time
            self.results.append([arm,train_loss,val_acc,test_acc,duration])
            print arm
            print n_units,val_acc,test_acc, duration/60.0
            if calc_test_error:
                return numpy.array([[[numpy.log(1-val_acc)]],[[duration]],[[numpy.log(1-test_acc)]]])
            return numpy.array([[[numpy.log(1-val_acc)]],[[duration]]])

        except Exception:
            raise Exception  # rethrowing exception to break out of parent
    def run(self):
        X_lower,X_upper=self.get_hp_ranges()
        fabolas_fmin(self.objective_function,X_lower,X_upper,self.dir,total_time=self.runtime,test_func=functools.partial(self.objective_function,calc_test_error=True))


def main(argv):

    model=''
    data_dir=''
    output_dir=''
    seed_id=0
    device_id=0
    try:
        opts, args = getopt.getopt(argv,"hm:i:o:s:d:",['model=','input_dir=','output_dir=','seed=','device='])
    except getopt.GetoptError:
        print 'hyperband_alg.py -m <model> -i <data_dir> -o <output_dir> -s <rng_seed> -d <GPU_id>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'hyperband_alg.py -i <data_dir> -o <output_dir> -s <rng_seed> -d <GPU_id>'
            sys.exit()
        elif opt in ("-m", "--model"):
            model = arg
        elif opt in ("-i", "--input_dir"):
            data_dir = arg
        elif opt in ("-o", "--output_dir"):
            output_dir = arg
        elif opt in ("-s", "--seed"):
            seed_id = int(arg)
        elif opt in ("-d", "--device"):
            device_id= int(arg)
    dir=output_dir+'/trial'+str(seed_id)
    #Starting 6 used increasing budget, before used constant budget for max metaarms
    if not os.path.exists(dir):
        os.makedirs(dir)
    sys.stdout = Logger(dir)
    if model=='cifar10':
        from cifar10.cifar10_helper import get_cnn_search_space,cifar10_conv
        params = get_cnn_search_space()
        obj=cifar10_conv(data_dir,device=device_id,seed=seed_id,max_iter=5000)
        searcher=fabolas_search(params,obj,'iter',30000/2.5,3600*48,dir,50,2000)
        searcher.run()

    elif model=='svhn':
        from svhn.svhn_helper import get_cnn_search_space,svhn_conv
        params = get_cnn_search_space()
        obj=svhn_conv(data_dir,device=device_id,seed=seed_id)
        searcher=fabolas_search(params,obj,'iter',60000*50,3600*48,dir,100,60000)
        searcher.run()
    elif model=='mrbi':
        from mrbi.mrbi_helper import get_cnn_search_space,mrbi_conv
        params = get_cnn_search_space()
        obj=mrbi_conv(data_dir,device=device_id,seed=seed_id)
        searcher=fabolas_search(params,obj,'iter',30000*50,3600*48,dir,100,30000)
        searcher.run()
    elif model=='cifar100':
        from networkin.nin_helper import get_nin_search_space,nin_conv
        params = get_nin_search_space()
        obj=nin_conv("cifar100",data_dir,device_id,seed_id)
        searcher=fabolas_search(params,obj,'iter',60000*50,3600*48,dir,100,60000)
        searcher.run()
    elif model=='cifar10_svm':
        from svm.svm_helper import get_svm_search,svm_model
        params= get_svm_search()
        obj=svm_model('cifar10',data_dir,seed_id)
        n_obs=len(obj.orig_data['y_train'])
        searcher=fabolas_search(params,obj,'iter',n_obs*50,3600*48,dir,100,n_obs)
        searcher.run()
    elif model=='cifar10_random_features':
        from svm.random_features_helper import get_svm_search,random_features_model
        params=get_svm_search()
        obj=random_features_model('cifar10',data_dir,seed=seed_id)
        searcher=fabolas_search(params,obj,'iter',100000*50,3600*48,dir,100,100000)
        searcher.run()


if __name__ == "__main__":
    main(sys.argv[1:])
