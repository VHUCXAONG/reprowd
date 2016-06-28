import pbclient
import sqlite3
import requests
import time
from collections import namedtuple

global_class_name = []#used to prevent duplicated class name
class CrowdData:
    def __init__(self, endpoint, api_key, data, crowd_data_name = "crowdbase",
                short_name = "short_name", description = "description"):
        while crowd_data_name in global_class_name:
            crowd_data_name += "_1"
            print "class name already eixsts, change it to _1"
        global_class_name.append(crowd_data_name)
        initial_presenter_name = ['img']
        initial_presenter_path = ['presenter/img.html']
        self.presenter = {'name':initial_presenter_name, 'path':initial_presenter_path}
        self.cd_name = crowd_data_name
        self.short_name = short_name
        self.description = description
        self.cache_result = {}
        id_list = [i for i in range(len(data))]
        self.cd = {'data':data, 'id_list':id_list}
        self.cols = ["data", "id_list"]
        self.presenter_projectid = {}

        for p in self.presenter['name']:
            self.presenter_projectid[p] = -1

        pbclient.set('endpoint', endpoint)
        pbclient.set('api_key', api_key)
        self.cddb = sqlite3.connect('crowddata.db')
        self.cur = self.cddb.cursor()
        try:
            exe_str = "CREATE TABLE " + self.cd_name + " (id integer, col_name varchar(100), value text DEFAULT NULL, PRIMARY KEY(id, col_name))"
            self.cur.execute(exe_str)
        except:
            pass
    #once there is a request, firstly check if there is an updated result in cache_result
    #if not, need to call pybossa get_taskruns to get the newest result
    #meanwhile update all results of tasks in the same project
    def get_result(self, task, n):
        #task is a json stored in self.cd['task']
        result = []
        if str(task['id']) in self.cache_result and len(self.cache_result[str(task['id'])]) > n:
            return self.cache_result[str(task['id'])]
        results = pbclient.get_taskruns(task['project_id'])
        for r in results:
            if str(r.data['task_id']) not in self.cache_result:
                self.cache_result[str(r.data['task_id'])] = []
            if r.data not in self.cache_result[str(r.data['task_id'])]:
                self.cache_result[str(r.data['task_id'])].append(r.data)
            if (r.data['task_id'] == task['id']):
                result.append(r.data)
        return result

    def addPresenter(self, name, path):
        if len(name) != len(path):
            print "number of name and path unmatched"
            return
        for i, j in enumerate(zip(name, path)):
            if i in self.presenter['name']:
                i += "_1"
                print "presenter name already exists, change it to _1"
            self.presenter['name'].append(i)
            self.presenter['path'].append(j)
            self.presenter_projectid[i] = -1
            assert len(self.presenter['name']) == len(self.presenter['path'])

    def map(self, func, output_col):
        if output_col in self.cols:
            print "output_col already exists"
            return
        n = len(self.cd['id_list'])
        self.cd[output_col] = n * [None]
        Row = namedtuple("Row", self.cols)
        for i in range(n):
            row = Row(*[self.cd[col][i] for col in self.cols])
            self.cd[output_col][i] = func(row)
        self.cols.append(output_col)
        return self

    def createTask(self, input_col = "data", output_col = "task", presenter = "img", n_answers = 30, priority_0 = 0, quorum = 0):
        if presenter not in self.presenter['name']:
            print "presenter doesn't exist"
            return
        if input_col not in self.cols:
            print "input error1" #jn: need to return a more clear error info. We can work on this later.
            return
        while output_col in self.cols:
            print "output already exisits" #jn: need to return a more clear error info. We can work on this later
            output_col = output_col + "_1"
        self.cols.append(output_col)
        if self.presenter_projectid[presenter] == -1:
            p = pbclient.create_project(self.cd_name + "_" + presenter, self.short_name + "_" + presenter, self.description + "_" + presenter)
            self.presenter_projectid[presenter] = p.id
            index = self.presenter['name'].index(presenter)
            p.info['task_presenter'] = open(self.presenter['path'][index]).read()
            pbclient.update_project(p)

        self.cd[output_col] = [None] * len(self.cd[input_col])
        assert len(self.cd["id_list"]) == len(self.cd[input_col])
        for k, (i, d) in enumerate(zip(self.cd["id_list"], self.cd[input_col])):
            exe_str = "SELECT * FROM " + self.cd_name + " WHERE id=? AND col_name=?"
            self.cur.execute(exe_str, (i, output_col, ))
            data = self.cur.fetchall()
            if data != []:
                assert len(data) == 1
                self.cd[output_col][k] = eval(data[0][2])
                continue

            task_info = d
            task = pbclient.create_task(self.presenter_projectid[presenter], task_info, n_answers, priority_0, quorum)
            exe_str = "INSERT INTO " + self.cd_name + " VALUES(?,?,?)"
            self.cur.execute(exe_str, (i, output_col, str(task.data), ))
            self.cddb.commit()
            self.cd[output_col][k] = task.data


        return self

    def getTaskResult(self, input_col = "task", output_col = "result", loop_interval = 10,
                    stop_condition = lambda result, n: len(result) == n):
        if input_col not in self.cols:
            print "input error2"  #see my previous comment
            return
        while output_col in self.cols:
            print "output already exisits" #see my previous commemt
            output_col = output_col + "_1"
        self.cols.append(output_col)
        self.cd[output_col] = [[]] * len(self.cd[input_col])
        assert len(self.cd["id_list"]) == len(self.cd[input_col])

        complete = [0] * len(self.cd[input_col])#used to check stop condition
        rn = 0
        while rn < len(self.cd[input_col]):
            for k, (i, d) in enumerate(zip(self.cd["id_list"], self.cd[input_col])):
                if complete[k] == 1:
                    continue
                if self.cd[output_col][k] == []:
                    exe_str = "SELECT * FROM " + self.cd_name + " WHERE id=? AND col_name=?"
                    self.cur.execute(exe_str, (i, output_col, ))
                    data = self.cur.fetchall()
                    if data != []:
                        assert len(data) == 1
                        self.cd[output_col][k] = eval(data[0][2])
                        if stop_condition(self.cd[output_col][k], d['n_answers']):
                            #check stop condition
                            complete[k] = 1
                            rn += 1
                            continue

                result = self.get_result(d, len(self.cd[output_col][k]))
                if len(result) > 0:
                    exe_str = "INSERT OR REPLACE INTO " + self.cd_name + " (id, col_name, value) VALUES(?,?,?)"
                    self.cur.execute(exe_str, (i, output_col, str(result), ))
                    self.cddb.commit()
                    self.cd[output_col][k] = result
                    if stop_condition(self.cd[output_col][k], d['n_answers']):
                        complete[k] = 1
                        rn += 1
                        continue
            time.sleep(loop_interval)
        return self

    def __del__(self):
        self.cur.close()
        self.cddb.close()

if __name__ == "__main__":
    data = ['http://farm4.static.flickr.com/3114/2524849923_1c191ef42e.jpg', 'http://www.7-star-admiral.com/0015_animals/0629_angora_hamster_clipart.jpg']
    cd = CrowdData('http://localhost:7000/', '8df67fd6-9c9b-4d32-a6ab-b0b5175aba30', data, "test24", "test24", "test24")
    def test(row):
        return {'url_b':row.data}
    cd.map(test, "presenter_data").createTask("presenter_data", "task", "img", n_answers = 2).getTaskResult("task", "result", stop_condition = lambda result, n: len(result) >= n)
    print cd.cd["task"]
    print cd.cd["result"]
