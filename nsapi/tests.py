from secret import username, password
from treinplanner import treinplanner
from prijzen import prijzen
from stations import stations
from avt import avt
from storingen import storingen

treinplanner = treinplanner(username, password)
x = planner.fetchandparse('ut', 'apd', previous_advices=1, next_advices=1)

prijzen = prijzen(username, password)
x = prijzen.fetchandparse('ehv', 'bet')

stations = stations(username, password)
x = stations.fetchandparse()

avt = avt(username, password)
x = avt.fetchandparse('vb')

storingen = storingen(username, password)
x = storingen.fetchandparse()
