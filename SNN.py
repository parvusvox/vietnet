import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchvision.transforms as transforms

from SNNComponents import SpikingNeuronLayerRNN
from SNNComponents import OutputDataToSpikingPerceptronLayer
from SNNComponents import InputDataToSpikingPerceptronLayer

class SpikingNet(nn.Module):
    def __init__(self, device, n_time_steps, begin_eval):
        super(SpikingNet, self).__init__()
        assert( 0 <= begin_eval and begin_eval < n_time_steps)
        self.deice = device
        self.n_time_steps = n_time_steps
        self.begin_eval = begin_eval

        self.input_conversion = InputDataToSpikingPerceptronLayer(device)

        self.layer1 = SpikingNeuronLayerRNN(
            device, n_inputs=28*28, n_hidden=100, decay_multiplier=0.9, threshold=1.0, penalty_threshold=1.5)

        self.layer2 = SpikingNeuronLayerRNN(
            device, n_inputs=100, n_hidden=10, decay_multiplier=0.9, threshold=1.0, penalty_threshold=1.5)

        self.all_layers = [self.layer1, self.layer2]

        self.output_conversion = OutputDataToSpikingPerceptronLayer(average_output=False)

        self.to(device)

    def forward_through_time(self, x):
        self.input_conversion.reset_state()
        for layer in self.all_layers:
            layer.reset_state()

        out = []
        
        all_states = []
        all_outputs = []

        for _ in range(self.n_time_steps):
            xi = self.input_conversion(x)
            prev_layer_state, prev_layer_output = None, xi
            for layer in self.all_layers:
                layer_state, layer_output = layer(prev_layer_output)
                prev_layer_state, prev_layer_output = layer_state, layer_output

                all_states.append(layer_state)
                all_outputs.append(layer_output)

            out.append(prev_layer_state)
        out = self.output_conversion(out[self.begin_eval:])
        return out, [[layer_states, layer_outputs] 
                     for layer_states, layer_outputs in zip(all_states, all_outputs)]

    def _DEP_forward_through_time(self, x):
        self.input_conversion.reset_state()
        self.layer1.reset_state()
        self.layer2.reset_state()

        out = []

        all_layer1_states = []
        all_layer1_outputs = []

        all_layer2_states = []
        all_layer2_outputs = []

        for _ in range(self.n_time_steps):
            xi = self.input_conversion(x)

            layer1_state, layer1_output = self.layer1(xi)
            layer2_state, layer2_output = self.layer2(layer1_output)

            all_layer1_states.append(layer1_state)
            all_layer1_outputs.append(layer1_output)

            all_layer2_states.append(layer2_state)
            all_layer2_outputs.append(layer2_output)
            out.append(layer2_state)

        out = self.output_conversion(out[self.begin_eval:])
        return out, [[all_layer1_states, all_layer1_outputs],
                     [all_layer2_states, all_layer2_outputs]]


    def forward(self, x):
        out, _ = self.forward_through_time(x)
        return F.log_softmax(out, dim=-1)


    def visualize_all_neurons(self, x):

        assert x.shape[0] == 1 and len(x.shape) == 4, (

            "Pass only 1 example to SpikingNet.visualize(x) with outer dimension shape of 1.")
        _, layers_state = self.forward_through_time(x)

        for i, (all_layer_states, all_layer_outputs) in enumerate(layers_state):
            layer_state  =  torch.stack(all_layer_states).data.cpu(
                ).numpy().squeeze().transpose()
            layer_output = torch.stack(all_layer_outputs).data.cpu(
                ).numpy().squeeze().transpose()


            self.plot_layer(layer_state, title="Inner state values of neurons for layer {}".format(i))
            self.plot_layer(layer_output, title="Output spikes (activation) values of neurons for layer {}".format(i))

    def visualize_neuron(self, x, layer_idx, neuron_idx):
        assert x.shape[0] == 1 and len(x.shape) == 4, (
            "Pass only 1 example to SpikingNet.visualize(x) with outer dimension shape of 1.")
        _, layers_state = self.forward_through_time(x)

        all_layer_states, all_layer_outputs = layers_state[layer_idx]
        layer_state  =  torch.stack(all_layer_states).data.cpu(
            ).numpy().squeeze().transpose()
        layer_output = torch.stack(all_layer_outputs).data.cpu(
            ).numpy().squeeze().transpose()

        self.plot_neuron(
            layer_state[neuron_idx],
            title="Inner state values neuron {} of layer {}".format(neuron_idx, layer_idx))
        self.plot_neuron(
            layer_output[neuron_idx],
            title="Output spikes (activation) values of neuron {} of layer {}".format(neuron_idx, layer_idx))

    def plot_layer(self, layer_values, title):
        """
        This function is derived from:
            https://github.com/guillaume-chevalier/LSTM-Human-Activity-Recognition
        Which was released under the MIT License.
        """
        width = max(16, layer_values.shape[0] / 8)
        height = max(4, layer_values.shape[1] / 8)
        plt.figure(figsize=(width, height))
        plt.imshow(
           layer_values,
            interpolation="nearest",
            cmap=plt.cm.rainbow
        )

        plt.title(title)
        plt.colorbar()
        plt.xlabel("Time")
        plt.ylabel("Neurons of layer")
        plt.show()

    def plot_neuron(self, neuron_through_time, title):
        width = max(16, len(neuron_through_time) / 8)
        height = 4
        plt.figure(figsize=(width, height))
        plt.title(title)
        plt.plot(neuron_through_time)
        plt.xlabel("Time")
        plt.ylabel("Neuron's activation")
        plt.show()

if __name__ == "__main__":
    from util import download_mnist
    from util import test, train, train_many_epochs
    from SNN import SpikingNet

    batch_size = 1000
    DATA_PATH = './data'

    training_set, testing_set = download_mnist(DATA_PATH)
    train_set_loader = torch.utils.data.DataLoader(
        dataset=training_set,
        batch_size=batch_size,
        shuffle=True)

    test_set_loader = torch.utils.data.DataLoader(
        dataset=testing_set,
        batch_size=1,
        shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    spiking_model = SpikingNet(device, n_time_steps = 128, begin_eval=0)
    train_many_epochs(spiking_model, device, train_set_loader, test_set_loader)
