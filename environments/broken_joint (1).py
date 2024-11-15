import gym
import numpy as np


class BrokenJointEnv(gym.Wrapper):
    def __init__(self, env, broken_joints,p = 1):
        super(BrokenJointEnv, self).__init__(env)
        self.observation_space = gym.spaces.Box(
            low=self.observation_space.low,
            high=self.observation_space.high,
            dtype=np.float32,
        )
        self.p = p
        self._max_episode_steps = env._max_episode_steps
        if broken_joints is not None:
            for broken_joint in broken_joints:
                assert 0 <= broken_joint <= len(self.action_space.low) - 1
        self.broken_joints = broken_joints

    def step(self, action: np.ndarray):
        action = np.array(action)
        if self.broken_joints is not None:
            if np.random.random() < self.p:
                for broken_joint in self.broken_joints:
                    action[broken_joint] = 0
            else:
                action=action
        return super(BrokenJointEnv, self).step(action)


class BrokenJointEnv2(gym.Wrapper):
    def __init__(self, env, broken_joints):
        super(BrokenJointEnv2, self).__init__(env)
        self.observation_space = gym.spaces.Box(
            low=self.observation_space.low,
            high=self.observation_space.high,
            dtype=np.float32,
        )
        self._max_episode_steps = env._max_episode_steps
        if broken_joints is not None:
            for broken_joint in broken_joints:
                assert 0 <= broken_joint <= len(self.action_space.low) - 1
        self.broken_joints = broken_joints

    def step(self, action: np.ndarray):
        action = np.array(action)
        if self.broken_joints is not None:
            for broken_joint in self.broken_joints:
                if action[broken_joint] > 0.1:
                    action[broken_joint] = 0.1
                if action[broken_joint] < -0.1:
                    action[broken_joint] = -0.1
        return super(BrokenJointEnv2, self).step(action)
