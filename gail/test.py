import numpy as np


def evaluate_model(agent, env, state_rms, action_bounds):
    total_rewards = 0
    s = env.reset()[0]
    done = False
    t = 0
    while not done:
        # s = np.clip((s - state_rms.mean) / (state_rms.var ** 0.5 + 1e-8), -5.0, 5.0)
        dist = agent.choose_dist(s)
        action = dist.sample().cpu().numpy()[0]
        # action = np.clip(action, action_bounds[0], action_bounds[1])
        next_state, reward, done, _,_ = env.step(action)
        # env.render()
        s = next_state
        total_rewards += reward
        t += 1
        if t == 200:
            break
    # env.close()
    return total_rewards
