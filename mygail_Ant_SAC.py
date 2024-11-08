
import gym
import torch
import numpy as np
import argparse
import matplotlib.pyplot as plt
import torch.nn as nn
import torch.optim as optim
from collections import deque
import sys
 
import gym
import os
import mujoco_py
from gail.model import Agent
from gail.train import Train
import gym
import numpy as np
from models.darc import DARC
from models.gail import GAIL
from models.sac import ContSAC

from environments.broken_joint import BrokenJointEnv
import os


# sys.argv = ['run.py']
 
parser = argparse.ArgumentParser()
parser.add_argument('--env_name', type=str, default="Humanoid-v2",
                    help='name of Mujoco environement')
args = parser.parse_args()

env = BrokenJointEnv(gym.make('Ant-v2'), [])
# train_taregt_env = BrokenJointEnv(gym.make('Ant-v2'), target_broken)

N_S = env.observation_space.shape[0]
N_A = env.action_space.shape[0]


policy_config = {
    "input_dim": [N_S],
    "architecture": [{"name": "linear1", "size": 256},
                    {"name": "linear2", "size": 256},
                    {"name": "split1", "sizes": [N_A, N_A]}],
    "hidden_activation": "relu",
    "output_activation": "none"
}

value_config = {
    "input_dim": [N_S  + N_A],
    "architecture": [{"name": "linear1", "size": 256},
                    {"name": "linear2", "size": 256},
                    {"name": "linear2", "size": 1}],
    "hidden_activation": "relu",
    "output_activation": "none"
}


sa_config = {
    "input_dim": [N_S + N_A],
    "architecture": [{"name": "linear1", "size": 64},
                    {"name": "linear2", "size": 2}],
    "hidden_activation": "relu",
    "output_activation": "none"
}
sas_config = {
    "input_dim": [N_S * 2 + N_A],
    "architecture": [{"name": "linear1", "size": 64},
                    {"name": "linear2", "size": 2}],
    "hidden_activation": "relu",
    "output_activation": "none"
}
expert = ContSAC(policy_config, value_config, env, "cpu", ent_adj=True,
             n_updates_per_train=1,lr=3e-4,max_steps=200,batch_size=256)
expert_path = 'Ant-v2-sac-200steps_20230504'
expert.load_model(expert_path, "cpu")


##parameters
lr_actor = 0.0003
lr_critic = 0.0003
lr_dis = 0.0003
Iter = 1200
MAX_STEP = 200
gamma = 0.98
lambd = 0.98
batch_size_dis = 256
batch_size = 256
epsilon = 0.2
l2_rate = 0.001
Horizon = 2048

class Actor(nn.Module):
    def __init__(self, N_S, N_A):
        super(Actor, self).__init__()
        self.fc1 = nn.Linear(N_S, 256)
        self.fc2 = nn.Linear(256,256)
        self.sigma = nn.Linear(256, N_A)
        self.mu = nn.Linear(256, N_A)
        self.mu.weight.data.mul_(0.1)
        self.mu.bias.data.mul_(0.0)
        # self.set_init([self.fc1,self.fc2, self.mu, self.sigma])
        self.distribution = torch.distributions.Normal
 
    # 初始化网络参数
    # def set_init(self, layers):
    #     for layer in layers:
    #         nn.init.normal_(layer.weight, mean=0., std=0.1)
    #         nn.init.constant_(layer.bias, 0.)
 
    def forward(self, s):
        x = torch.tanh(self.fc1(s))
        x = torch.tanh(self.fc2(x))
 
        mu = self.mu(x)
        log_sigma = self.sigma(x)
        # log_sigma = torch.zeros_like(mu)
        sigma = torch.exp(log_sigma)
        return mu, sigma
 
    def choose_action(self, s):
        mu, sigma = self.forward(s)
        Pi = self.distribution(mu, sigma)
        return Pi.sample().numpy()
    
    def choose_action_det(self, s):
        mu, sigma = self.forward(s)
        return mu.detach().numpy()
 
 
# Critic网洛
class Critic(nn.Module):
    def __init__(self, N_S):
        super(Critic, self).__init__()
        self.fc1 = nn.Linear(N_S, 256)
        self.fc2 = nn.Linear(256, 256)
        self.fc3 = nn.Linear(256, 1)
        self.fc3.weight.data.mul_(0.1)
        self.fc3.bias.data.mul_(0.0)
        # self.set_init([self.fc1, self.fc2, self.fc2])
 
    # def set_init(self, layers):
    #     for layer in layers:
    #         nn.init.normal_(layer.weight, mean=0., std=0.1)
    #         nn.init.constant_(layer.bias, 0.)
 
    def forward(self, s):
        x = torch.tanh(self.fc1(s))
        x = torch.tanh(self.fc2(x))
        values = self.fc3(x)
        return values

class Discriminator(nn.Module):
    def __init__(self, N_S,N_A):
        super(Discriminator, self).__init__()
        self.fc1 = nn.Linear(N_S + N_S, 256,bias=True)
        self.fc2 = nn.Linear(256, 256,bias=True)
        self.fc3 = nn.Linear(256, 1,bias=True)
        # self.fc3.weight.data.mul_(0.1)
        # self.fc3.bias.data.mul_(0.0)
        # self.set_init([self.fc1, self.fc2, self.fc2])
 
    # def set_init(self, layers):
    #     for layer in layers:
    #         nn.init.normal_(layer.weight, mean=0., std=0.1)
    #         nn.init.constant_(layer.bias, 0.)
 
    def forward(self, s):
        x = torch.relu(self.fc1(s))
        x = torch.relu(self.fc2(x))
        values = self.fc3(x)
        return values
    
    def predict_reward(self,state,action):
        state = torch.tensor(state).unsqueeze(0)
        action = torch.FloatTensor(action).unsqueeze(0)

        input = torch.cat([state,action],axis = 1)
        D = torch.sigmoid(self.forward(input.to(torch.float32)))
        reward = torch.log(1-D + 1e-6) - torch.log(D + 1e-6)
        reward = - torch.log(D )
        reward =  reward
        return reward
    
    def predict_reward_tensor(self,state,action,next_state):
        input = torch.cat([state,next_state],axis = 1)
        D = torch.sigmoid(self.forward(input.to(torch.float32)))
        # reward = torch.log(1-D + 1e-6) - torch.log(D + 1e-6)
        reward = - torch.log(D + 1e-6)
        # print(reward)
        for t in reward:
            if t > 100:
                print(t)

        return reward
 
 
 
class Ppo:
    def __init__(self, N_S, N_A):
        self.actor_net = Actor(N_S, N_A)
        self.critic_net = Critic(N_S)
        self.actor_optim = optim.Adam(self.actor_net.parameters(), lr=lr_actor)
        self.critic_optim = optim.Adam(self.critic_net.parameters(), lr=lr_critic, weight_decay=l2_rate)
        self.critic_loss_func = torch.nn.MSELoss()

        self.scheduler_actor = torch.optim.lr_scheduler.StepLR(self.actor_optim,step_size=2, gamma=0.98)
        self.scheduler_critic = torch.optim.lr_scheduler.StepLR(self.critic_optim,step_size=2, gamma=0.98)
    def scheduler(self):
        self.scheduler_actor.step()
        self.scheduler_critic.step()

    def train(self, memory):
        memory = np.array(memory)
        states = torch.tensor(np.vstack(memory[:, 0]), dtype=torch.float32)
 
        actions = torch.tensor(list(memory[:, 1]), dtype=torch.float32)
        rewards = torch.tensor(list(memory[:, 2]), dtype=torch.float32)
        masks = torch.tensor(list(memory[:, 3]), dtype=torch.float32)

        state_ori = torch.tensor(list(memory[:, 4]), dtype=torch.float32)
        next_state_ori = torch.tensor(list(memory[:, 5]), dtype=torch.float32) 
        next_state = torch.tensor(list(memory[:, 6]), dtype=torch.float32) 
        

        rewards = discriminator.predict_reward_tensor(states,actions,next_state).squeeze(1).detach().numpy()
        values = self.critic_net(states)
 
        returns, advants = self.get_gae(rewards, masks, values)
        old_mu, old_std = self.actor_net(states)
        pi = self.actor_net.distribution(old_mu, old_std)
 
        old_log_prob = pi.log_prob(actions).sum(1, keepdim=True)
 
        n = len(states)
        arr = np.arange(n)
        for epoch in range(5):
            np.random.shuffle(arr)
            for i in range(n // batch_size):

                b_index = arr[batch_size * i:batch_size * (i + 1)]
                b_states = states[b_index]
                b_advants = advants[b_index].unsqueeze(1)
                b_actions = actions[b_index]
                b_returns = returns[b_index].unsqueeze(1)
 
                mu, std = self.actor_net(b_states)
                pi = self.actor_net.distribution(mu, std)
                new_prob = pi.log_prob(b_actions).sum(1, keepdim=True)
                old_prob = old_log_prob[b_index].detach()
                ratio = torch.exp(new_prob - old_prob)
 
                surrogate_loss = ratio * b_advants
                values = self.critic_net(b_states)
 
                critic_loss = self.critic_loss_func(values, b_returns)
 
                self.critic_optim.zero_grad()
                critic_loss.backward()
                self.critic_optim.step()
 
                ratio = torch.clamp(ratio, 1.0 - epsilon, 1.0 + epsilon)
 
                clipped_loss = ratio * b_advants
 
                actor_loss = -torch.min(surrogate_loss, clipped_loss).mean()
 
                self.actor_optim.zero_grad()
                actor_loss.backward()
 
                self.actor_optim.step()
 
    # 计算GAE
    def get_gae(self, rewards, masks, values):
        rewards = torch.Tensor(rewards)
        masks = torch.Tensor(masks)
        returns = torch.zeros_like(rewards)
        advants = torch.zeros_like(rewards)
        running_returns = 0
        previous_value = 0
        running_advants = 0
 
        for t in reversed(range(0, len(rewards))):
            # 计算A_t并进行加权求和
            running_returns = rewards[t] + gamma * running_returns * masks[t]
            running_tderror = rewards[t] + gamma * previous_value * masks[t] - \
                              values.data[t]
            running_advants = running_tderror + gamma * lambd * \
                              running_advants * masks[t]
 
            returns[t] = running_returns
            previous_value = values.data[t]
            advants[t] = running_advants
        # advants的归一化
        advants = (advants - advants.mean()) / advants.std()
        return returns, advants



 
 
class Nomalize:
    def __init__(self, N_S):
        self.mean = np.zeros((N_S,))
        self.std = np.zeros((N_S,))
        self.stdd = np.zeros((N_S,))
        self.n = 0
 
    def __call__(self, x):
        # x = np.asarray(x)
        # self.n += 1
        # if self.n == 1:
        #     self.mean = x
        # else:
        #     # 更新样本均值和方差
        #     old_mean = self.mean.copy()
        #     self.mean = old_mean + (x - old_mean) / self.n
        #     self.stdd = self.stdd + (x - old_mean) * (x - self.mean)
        #     # 状态归一化
        # if self.n > 1:
        #     self.std = np.sqrt(self.stdd / (self.n - 1))
        # else:
        #     self.std = self.mean
        # x = x - self.mean
        # x = x / (self.std + 1e-8)
        # x = np.clip(x, -5, +5)
        return x
 

ppo = Ppo(N_S, N_A)
nomalize = Nomalize(N_S)


discriminator = Discriminator(N_S,N_A)
discriminator_opt = optim.Adam(discriminator.parameters(), lr=lr_dis)



memory_expert = deque()
def get_expert_action(expert, state, deterministic=True):
    with torch.no_grad():
        state = torch.as_tensor(state[np.newaxis, :].copy(), dtype=torch.float32).to('cpu')
        if deterministic:
            _, action_prob, action = expert.policy.sample(state)
        else:
            action, action_prob, _ = expert.policy.sample(state)
        return action.detach().cpu().numpy()[0], action_prob.detach().cpu().numpy()[0]
    

def sample_expert_data(expert,memory_expert,env):
    
    total_rewards = 0
    n_steps = 0
    done = False
    state = env.reset()
    states = []
    actions = []
    rr = 0
    for k in range(1):
        n_steps = 0
        state = env.reset()
        done = False
        while not done:
            action,_ = get_expert_action(expert, state, deterministic = False)
            next_state, reward, done, _ = env.step(action)
            done_mask = 1.0 if n_steps == 200 else float(not done)
            if n_steps == 200:
                done = True
            rr += reward
            memory_expert.append((state, action, reward, next_state, done_mask,nomalize(state),nomalize(next_state)))
            n_steps += 1
            
            total_rewards += reward
            states.append(state)
            actions.append(action)
            state = next_state
    # print(total_rewards)
    return memory_expert

def sample_expert_data_target(expert,memory_expert,env):
    
    total_rewards = 0
    n_steps = 0
    done = False
    state = env.reset()
    states = []
    actions = []
    rr = 0
    for k in range(30):
        n_steps = 0
        state = env.reset()
        done = False
        while not done:
            action,_ = get_expert_action(expert, state, deterministic = True)
            next_state, reward, done, _ = env.step(action)
            done_mask = 1.0 if n_steps == 200 else float(not done)
            if n_steps == 200:
                done = True
            rr += reward
            memory_expert.append((state, action, reward, next_state, done_mask,nomalize(state),nomalize(next_state)))
            n_steps += 1
            
            total_rewards += reward
            states.append(state)
            actions.append(action)
            state = next_state
    print(total_rewards/30)
    return memory_expert

def update_discriminator(memory_expert,memory,discriminator,optimizer):
    memory = np.array(memory)
    state = torch.tensor(np.vstack(memory[:, 0]), dtype=torch.float32)
    actions = torch.tensor(list(memory[:, 1]), dtype=torch.float32)
    states_or = torch.tensor(np.vstack(memory[:, 4]), dtype=torch.float32)
    next_states_or = torch.tensor(np.vstack(memory[:, 5]), dtype=torch.float32)
    next_states = torch.tensor(np.vstack(memory[:, 6]), dtype=torch.float32)


    memory_expert = np.array(memory_expert)
    actions_exp = torch.tensor(list(memory_expert[:, 1]), dtype=torch.float32)
    states_exp = torch.tensor(np.vstack(memory_expert[:, 5]), dtype=torch.float32)
    next_states_exp = torch.tensor(np.vstack(memory_expert[:, 6]), dtype=torch.float32)
    

    len_data = np.arange(min(len(memory_expert),len(memory)))

    np.random.shuffle(memory_expert)

    output = torch.sigmoid(discriminator(torch.cat([state, next_states],axis = 1)))
    output_darc = torch.sigmoid(discriminator(torch.cat([states_exp,next_states_exp],axis = 1)))

    acc_learner = sum(output > 0.5)/len(output)
    acc_expert = sum(output_darc < 0.5)/len(output_darc)
    acc_all = (sum(output > 0.5) + sum(output_darc < 0.5))/(len(output_darc) + len(output))


    for epoch in range(1):
            np.random.shuffle(len_data)
            for i in range(min(len(memory_expert),len(memory)) // batch_size_dis):
                b_index = len_data[batch_size_dis * i:batch_size_dis * (i + 1)]

                b_states = states_or[b_index]
                b_actions = actions[b_index]
                b_next_states_or = next_states_or[b_index]


                b_states_exp = states_exp[b_index]
                b_actions_exp = actions_exp[b_index]
                b_next_states_exp = next_states_exp[b_index]
                b_states_behavior = state[b_index]                

                optimizer.zero_grad()
                output = torch.sigmoid(discriminator(torch.cat([b_states_behavior, b_next_states_or],axis = 1)))

                output_darc = torch.sigmoid(discriminator(torch.cat([b_states_exp,b_next_states_exp],axis = 1)))
                loss_fun = torch.nn.BCELoss()
                loss = -torch.mean( torch.log(output.squeeze(0) + 1e-8)) - torch.mean(torch.log(1-output_darc.squeeze(0) + 1e-8))

                loss.backward()
                optimizer.step()
    return acc_learner,acc_expert,acc_all




def eval_target(env,num):
    score = 0
    for k in range(num):
        s_origin = env.reset()
        s = nomalize(s_origin)
        for _ in range(MAX_STEP):
            act = ppo.actor_net.choose_action(torch.from_numpy(np.array(s).astype(np.float32)).unsqueeze(0))[0]
            s_, r, done, info = env.step(act)
            next_s_origin = s_
            s_ = nomalize(s_)
            mask = (1 - done) * 1
            score += r
            s = s_
            s_origin = next_s_origin
            if done:
                break
    return score/num
    
    


    



# memory_expert = sample_expert_data(expert,memory_expert,source_env)
episodes = 0
eva_episodes = 0
avg_rewards = []
show_episodes = []

eval_reward_list = []
acc_learner_list = []
acc_expert_list = []
reward_src_list = []
overall_acc_list = []

memory_expert = sample_expert_data_target(expert,memory_expert,env)
memory_expert = deque()
scheduler = torch.optim.lr_scheduler.StepLR(discriminator_opt, gamma=0.99,step_size = 2)
for t in range(80):
    memory_expert = sample_expert_data(expert,memory_expert,env)
for iter in range(Iter):
    memory = deque()
    scores = []
    steps = 0

    s_origin = env.reset()
    s = nomalize(s_origin)
    score = 0

    while steps < Horizon:  # Horizen
        episodes += 1
        s_origin = env.reset()
        s = nomalize(s_origin)
        score = 0
        for _ in range(MAX_STEP):
            if _ == 0:
                s_origin = env.reset()
                s = nomalize(s_origin)
                score = 0
            steps += 1
            act = ppo.actor_net.choose_action(torch.from_numpy(np.array(s).astype(np.float32)).unsqueeze(0))[0]
            s_, r, done, info = env.step(act)
            next_s_origin = s_
            s_ = nomalize(s_)
            mask = (1 - done) * 1
            memory.append([s, act, r, mask,s_origin,next_s_origin,s_])
            score += r
            s = s_
            s_origin = next_s_origin
            if done:
                break
                
        with open('log_' + args.env_name + '.txt', 'a') as outfile:
            outfile.write('\t' + str(episodes) + '\t' + str(score) + '\n')
        scores.append(score)

    score_avg = np.mean(scores)
    print('{} episode avg_reward is {:.2f}'.format(episodes, np.mean(scores)))
    reward_src_list.append(np.mean(scores))
    acc_learner, acc_darc,overall_acc = update_discriminator(memory_expert,memory,discriminator,discriminator_opt)
    acc_learner_list.append(acc_learner.item())
    acc_expert_list.append(acc_darc.item())
    overall_acc_list.append(overall_acc.item())

    ppo.train(memory)
    scheduler.step()

    # print('{} episode, the one episode eval_reward is {:.2f}'.format(episodes, eval_reward))

    if iter == 0:
        print(acc_learner, acc_darc)
    
    if iter%20 == 0 and iter !=0:
        print('acc_learner',acc_learner, 'acc_darc',acc_darc,'overall',overall_acc)

np.savetxt('savefile/ANT_SAC_eval_r.txt',eval_reward_list)
np.savetxt('savefile/ANT_SAC_r.txt',reward_src_list)

